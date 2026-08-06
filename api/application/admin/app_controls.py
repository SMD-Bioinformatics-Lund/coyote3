"""Application controls and operational retention settings."""

from __future__ import annotations

import gzip
import shutil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pymongo import ReturnDocument

from api.config.application_modules import APPLICATION_MODULES
from api.config.security import get_audit_events_collection_name, get_audit_retention_days
from api.contracts.schemas.app_controls import AppControlsDoc
from api.infra.request_context import current_username

APP_CONTROLS_COLLECTION = "app_controls"
APP_CONTROLS_ID = "default"
CELERY_INSPECTION_TIMEOUT_SECONDS = 1.5


def _task_summary(
    workers: dict[str, Any],
    *,
    state: str,
) -> list[dict[str, Any]]:
    """Return safe task metadata without exposing arguments or keyword arguments."""
    summaries: list[dict[str, Any]] = []
    for worker_name, task_rows in workers.items():
        for row in task_rows or []:
            if not isinstance(row, dict):
                continue
            task = row.get("request") if isinstance(row.get("request"), dict) else row
            delivery = task.get("delivery_info") or {}
            summaries.append(
                {
                    "worker": worker_name,
                    "state": state,
                    "task_id": task.get("id"),
                    "task_name": task.get("name"),
                    "queue": delivery.get("routing_key"),
                    "eta": row.get("eta") or task.get("eta"),
                    "started_at": task.get("time_start"),
                }
            )
    return sorted(
        summaries,
        key=lambda item: (
            str(item.get("task_name") or ""),
            str(item.get("task_id") or ""),
        ),
    )


def _worker_runtime_details(
    stats: dict[str, Any],
    active: dict[str, Any],
    reserved: dict[str, Any],
    scheduled: dict[str, Any],
    registered: dict[str, Any],
    active_queues: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize Celery worker statistics for the operational UI."""
    details: list[dict[str, Any]] = []
    for worker_name in sorted(stats):
        worker_stats = stats.get(worker_name) or {}
        pool = worker_stats.get("pool") or {}
        totals = worker_stats.get("total") or {}
        queues = sorted(
            {
                queue.get("name")
                for queue in (active_queues.get(worker_name) or [])
                if isinstance(queue, dict) and queue.get("name")
            }
        )
        details.append(
            {
                "name": worker_name,
                "status": "online",
                "pid": worker_stats.get("pid"),
                "uptime_seconds": worker_stats.get("uptime"),
                "pool": pool.get("implementation"),
                "concurrency": pool.get("max-concurrency"),
                "processed_count": sum(
                    int(value or 0) for value in totals.values() if isinstance(value, (int, float))
                ),
                "active_count": len(active.get(worker_name) or []),
                "reserved_count": len(reserved.get(worker_name) or []),
                "scheduled_count": len(scheduled.get(worker_name) or []),
                "registered_count": len(registered.get(worker_name) or []),
                "queues": queues,
            }
        )
    return details


def default_app_controls(config: dict[str, Any] | None = None) -> AppControlsDoc:
    """Build default application controls from runtime configuration."""
    config = config or {}
    controls = AppControlsDoc(
        control_id=APP_CONTROLS_ID,
        celery={
            "enabled": True,
            "sample_ingest_enabled": True,
            "collection_writes_enabled": True,
            "maintenance_enabled": True,
        },
        retention={
            "audit_events_days": get_audit_retention_days(config),
            "notification_days": int(config.get("NOTIFICATION_RETENTION_DAYS", 180) or 180),
            "disk_log_days": int(config.get("LOG_RETENTION_DAYS", 30) or 30),
            "gzip_disk_logs_after_days": int(config.get("LOG_GZIP_AFTER_DAYS", 1) or 1),
        },
        modules={
            "dna_analysis_enabled": True,
            "rna_analysis_enabled": True,
            "reports_enabled": True,
            "variant_search_enabled": True,
            "knowledgebases_enabled": True,
            "ingest_workspace_enabled": True,
            "assay_catalog_enabled": True,
        },
    )
    return controls


def merge_controls(defaults: AppControlsDoc, stored: dict[str, Any] | None) -> AppControlsDoc:
    """Merge stored control values onto typed defaults."""
    payload = defaults.model_dump(by_alias=True)
    if stored:
        for section in ("celery", "retention", "modules"):
            stored_section = stored.get(section)
            if isinstance(stored_section, dict):
                payload[section].update(
                    {key: value for key, value in stored_section.items() if key in payload[section]}
                )
        stored_celery = stored.get("celery") if isinstance(stored.get("celery"), dict) else {}
        if "sample_ingest_enabled" not in stored_celery:
            payload["celery"]["sample_ingest_enabled"] = bool(
                stored_celery.get("ingest_bundle_enabled", True)
                and stored_celery.get("ingest_dependents_enabled", True)
            )
        stored_modules = stored.get("modules") if isinstance(stored.get("modules"), dict) else {}
        if "dna_analysis_enabled" not in stored_modules and "dna_enabled" in stored_modules:
            payload["modules"]["dna_analysis_enabled"] = bool(stored_modules["dna_enabled"])
        if "rna_analysis_enabled" not in stored_modules and "rna_enabled" in stored_modules:
            payload["modules"]["rna_analysis_enabled"] = bool(stored_modules["rna_enabled"])
        for key in ("created_on", "updated_by", "updated_on"):
            if stored.get(key) is not None:
                payload[key] = stored[key]
    return AppControlsDoc.model_validate(payload)


def effective_audit_retention_days(db: Any, config: dict[str, Any]) -> int:
    """Return audit retention from controls, falling back to runtime config."""
    defaults = default_app_controls(config)
    stored = db[APP_CONTROLS_COLLECTION].find_one(
        {"control_id": APP_CONTROLS_ID},
        {"retention.audit_events_days": 1},
    )
    try:
        controls = merge_controls(defaults, stored)
        return controls.retention.audit_events_days
    except Exception:
        return defaults.retention.audit_events_days


class AppControlsService:
    """DB-backed runtime switches for modules, Celery tasks, and retention."""

    def __init__(
        self,
        db: Any,
        *,
        config: dict[str, Any],
        audit_service: Any | None = None,
        index_conflicts_provider: Any | None = None,
    ) -> None:
        self.collection = db[APP_CONTROLS_COLLECTION]
        self.config = config
        self.audit_service = audit_service
        self.index_conflicts_provider = index_conflicts_provider

    def get_controls(self) -> AppControlsDoc:
        """Return effective controls with stored overrides applied."""
        defaults = default_app_controls(self.config)
        stored = self.collection.find_one({"control_id": APP_CONTROLS_ID})
        return merge_controls(defaults, stored)

    def payload(self) -> dict[str, Any]:
        """Return controls and defaults for the admin UI."""
        defaults = default_app_controls(self.config)
        controls = self.get_controls()
        return {
            "controls": controls.model_dump(by_alias=True),
            "defaults": defaults.model_dump(by_alias=True),
            "runtime": self.runtime_status(),
            "module_definitions": [
                {
                    "key": module.key,
                    "control_field": module.control_field,
                    "label": module.label,
                    "description": module.description,
                }
                for module in APPLICATION_MODULES
            ],
        }

    def runtime_status(self) -> dict[str, Any]:
        """Return observed task runtime state for the admin controls UI."""
        controls = self.get_controls()
        observed_at = datetime.now(timezone.utc)
        status: dict[str, Any] = {
            "observed_at": observed_at,
            "celery": {
                "configured_enabled": controls.celery.enabled,
                "configured_families": {
                    "sample_ingest": controls.celery.sample_ingest_enabled,
                    "collection_writes": controls.celery.collection_writes_enabled,
                    "maintenance": controls.celery.maintenance_enabled,
                },
                "status": "unknown",
                "execution_state": "unknown",
                "workers_online": 0,
                "worker_names": [],
                "worker_details": [],
                "active_count": 0,
                "reserved_count": 0,
                "scheduled_count": 0,
                "registered_task_count": 0,
                "registered_tasks": [],
                "beat_schedule_count": 0,
                "beat_entries": [],
                "queue_names": [],
                "queue_consumers": {},
                "tasks": [],
                "inspection_timeout_seconds": CELERY_INSPECTION_TIMEOUT_SECONDS,
                "error": None,
            },
            "modules": {
                module.key: {
                    "enabled": bool(getattr(controls.modules, module.control_field)),
                    "label": module.label,
                }
                for module in APPLICATION_MODULES
            },
            "index_setup_conflicts": [],
        }
        if self.index_conflicts_provider is not None:
            try:
                conflicts = self.index_conflicts_provider()
                if isinstance(conflicts, list):
                    status["index_setup_conflicts"] = conflicts
            except Exception:
                status["index_setup_conflicts"] = []

        try:
            from api.celery_app import celery_app

            inspect = celery_app.control.inspect(timeout=CELERY_INSPECTION_TIMEOUT_SECONDS)
            # Active work is the most time-sensitive observation. Read it before
            # slower worker metadata so short jobs are less likely to finish first.
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            scheduled = inspect.scheduled() or {}
            stats = inspect.stats() or {}
            registered = inspect.registered() or {}
            active_queues = inspect.active_queues() or {}
            queue_names = {
                queue.get("name")
                for worker_queues in active_queues.values()
                for queue in (worker_queues or [])
                if isinstance(queue, dict)
            }
            queue_names.update(
                delivery.get("routing_key")
                for worker_tasks in active.values()
                for task in worker_tasks
                if isinstance(task, dict)
                for delivery in [task.get("delivery_info") or {}]
                if delivery.get("routing_key")
            )
            registered_tasks = sorted(
                {task for tasks in registered.values() for task in (tasks or [])}
            )
            queue_consumers: dict[str, list[str]] = {}
            for worker_name, worker_queues in active_queues.items():
                for queue in worker_queues or []:
                    if not isinstance(queue, dict) or not queue.get("name"):
                        continue
                    queue_consumers.setdefault(str(queue["name"]), []).append(worker_name)
            beat_entries = [
                {
                    "name": name,
                    "task": entry.get("task"),
                    "schedule": str(entry.get("schedule")),
                }
                for name, entry in sorted((celery_app.conf.beat_schedule or {}).items())
                if isinstance(entry, dict)
            ]
            workers_online = len(stats)
            if controls.celery.enabled:
                execution_state = "ready" if workers_online else "workers_missing"
            else:
                execution_state = (
                    "execution_disabled_workers_online" if workers_online else "execution_disabled"
                )
            status["celery"].update(
                {
                    "status": "online" if stats else "offline",
                    "execution_state": execution_state,
                    "workers_online": workers_online,
                    "worker_names": sorted(stats),
                    "worker_details": _worker_runtime_details(
                        stats,
                        active,
                        reserved,
                        scheduled,
                        registered,
                        active_queues,
                    ),
                    "active_count": sum(len(tasks or []) for tasks in active.values()),
                    "reserved_count": sum(len(tasks or []) for tasks in reserved.values()),
                    "scheduled_count": sum(len(tasks or []) for tasks in scheduled.values()),
                    "registered_task_count": len(registered_tasks),
                    "registered_tasks": registered_tasks,
                    "beat_schedule_count": len(beat_entries),
                    "beat_entries": beat_entries,
                    "queue_names": sorted(name for name in queue_names if name),
                    "queue_consumers": {
                        name: sorted(consumers)
                        for name, consumers in sorted(queue_consumers.items())
                    },
                    "tasks": [
                        *_task_summary(active, state="active"),
                        *_task_summary(reserved, state="reserved"),
                        *_task_summary(scheduled, state="scheduled"),
                    ],
                }
            )
        except Exception as exc:
            status["celery"].update(
                {
                    "status": "unavailable",
                    "execution_state": "inspection_unavailable",
                    "error": str(exc),
                }
            )
        return status

    def update_controls(
        self, payload: dict[str, Any], *, actor: Any | None = None
    ) -> dict[str, Any]:
        """Validate and persist a complete controls document."""
        current = self.get_controls().model_dump(by_alias=True)
        incoming = deepcopy(current)
        for section in ("celery", "retention", "modules"):
            if isinstance(payload.get(section), dict):
                incoming[section].update(payload[section])
        incoming["control_id"] = APP_CONTROLS_ID
        incoming["updated_by"] = getattr(actor, "username", None) or current_username()
        incoming["updated_on"] = datetime.now(timezone.utc)
        validated = AppControlsDoc.model_validate(incoming)
        update_doc = validated.model_dump(by_alias=True, exclude={"id_", "created_on"})
        saved = self.collection.find_one_and_update(
            {"control_id": APP_CONTROLS_ID},
            {"$set": update_doc, "$setOnInsert": {"created_on": datetime.now(timezone.utc)}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if self.audit_service is not None:
            self.audit_service.record(
                "app.controls.updated",
                "Application controls updated",
                category="admin",
                actor=actor,
                resource_type="app_controls",
                resource_id=APP_CONTROLS_ID,
                tags=["admin", "controls"],
                metadata={"sections": sorted(payload.keys())},
            )
        return {"controls": AppControlsDoc.model_validate(saved).model_dump(by_alias=True)}

    def task_enabled(self, task_family: str) -> bool:
        """Return whether a Celery task family is allowed to execute."""
        controls = self.get_controls().celery
        if not controls.enabled:
            return False
        return bool(getattr(controls, f"{task_family}_enabled", False))

    def module_enabled(self, module_key: str) -> bool:
        """Return whether a software-defined application module is available."""
        module = next((item for item in APPLICATION_MODULES if item.key == module_key), None)
        if module is None:
            raise ValueError(f"Unknown application module: {module_key}")
        return bool(getattr(self.get_controls().modules, module.control_field))

    def public_module_payload(self) -> dict[str, Any]:
        """Return non-sensitive effective module availability for route rendering."""
        controls = self.get_controls().modules
        return {
            "modules": {
                module.key: {
                    "enabled": bool(getattr(controls, module.control_field)),
                    "label": module.label,
                    "description": module.description,
                }
                for module in APPLICATION_MODULES
            }
        }

    def cleanup_audit_events(self) -> dict[str, Any]:
        """Delete audit events older than the configured retention horizon."""
        retention_days = self.get_controls().retention.audit_events_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        audit_collection = self.collection.database[get_audit_events_collection_name(self.config)]
        result = audit_collection.delete_many({"occurred_at": {"$lt": cutoff}})
        return {
            "retention_days": retention_days,
            "deleted": int(result.deleted_count),
            "cutoff": cutoff,
        }

    def cleanup_disk_logs(self) -> dict[str, Any]:
        """Gzip old plain-text logs and delete logs beyond retention."""
        controls = self.get_controls()
        retention = controls.retention
        log_root = Path(str(self.config.get("LOGS") or "logs")).expanduser()
        if not log_root.exists() or not log_root.is_dir():
            return {"log_root": str(log_root), "gzipped": 0, "deleted": 0, "status": "not_found"}

        now = datetime.now(timezone.utc)
        gzip_before = now - timedelta(days=retention.gzip_disk_logs_after_days)
        delete_before = now - timedelta(days=retention.disk_log_days)
        gzipped = 0
        deleted = 0
        for path in log_root.rglob("*.log*"):
            if not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified < delete_before:
                path.unlink(missing_ok=True)
                deleted += 1
                continue
            if path.suffix == ".gz" or modified >= gzip_before:
                continue
            gz_path = path.with_name(f"{path.name}.gz")
            if gz_path.exists():
                continue
            with path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink(missing_ok=True)
            gzipped += 1
        return {"log_root": str(log_root), "gzipped": gzipped, "deleted": deleted, "status": "ok"}

    def run_maintenance(self) -> dict[str, Any]:
        """Run configured retention maintenance."""
        controls = self.get_controls()
        if not controls.celery.enabled or not controls.celery.maintenance_enabled:
            return {"status": "disabled"}
        try:
            result = {
                "status": "ok",
                "audit": self.cleanup_audit_events(),
                "disk_logs": self.cleanup_disk_logs(),
            }
        except Exception as exc:
            if self.audit_service is not None:
                self.audit_service.record(
                    "maintenance.retention.failed",
                    "Retention maintenance failed",
                    severity="error",
                    category="operations",
                    outcome="failure",
                    resource_type="app_controls",
                    resource_id=APP_CONTROLS_ID,
                    tags=["operations", "maintenance", "retention"],
                    metadata={"error_type": type(exc).__name__},
                )
            raise
        if self.audit_service is not None:
            self.audit_service.record(
                "maintenance.retention.completed",
                "Retention maintenance completed",
                category="operations",
                outcome="success",
                resource_type="app_controls",
                resource_id=APP_CONTROLS_ID,
                tags=["operations", "maintenance", "retention"],
                metadata={
                    "audit_events_deleted": result["audit"]["deleted"],
                    "disk_logs_deleted": result["disk_logs"]["deleted"],
                    "disk_logs_gzipped": result["disk_logs"]["gzipped"],
                },
            )
        return result
