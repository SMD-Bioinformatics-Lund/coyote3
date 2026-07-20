"""Application controls and operational retention settings."""

from __future__ import annotations

import gzip
import shutil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pymongo import ReturnDocument

from api.contracts.schemas.app_controls import AppControlsDoc
from api.infra.request_context import current_username
from api.settings import get_audit_events_collection_name, get_audit_retention_days, to_bool

APP_CONTROLS_COLLECTION = "app_controls"
APP_CONTROLS_ID = "default"


def default_app_controls(config: dict[str, Any] | None = None) -> AppControlsDoc:
    """Build default application controls from runtime configuration."""
    config = config or {}
    controls = AppControlsDoc(
        control_id=APP_CONTROLS_ID,
        celery={
            "enabled": True,
            "ingest_watch_enabled": to_bool(
                config.get("COYOTE3_INGEST_WATCH_ENABLED"), default=False
            ),
            "ingest_bundle_enabled": True,
            "ingest_dependents_enabled": True,
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
            "dna_enabled": True,
            "rna_enabled": True,
            "reports_enabled": True,
            "ingest_workspace_enabled": True,
            "audit_ui_enabled": True,
            "assay_catalog_enabled": True,
        },
    )
    return controls


def merge_controls(defaults: AppControlsDoc, stored: dict[str, Any] | None) -> AppControlsDoc:
    """Merge stored control values onto typed defaults."""
    payload = defaults.model_dump(by_alias=True)
    if stored:
        for section in ("celery", "retention", "modules"):
            if isinstance(stored.get(section), dict):
                payload[section].update(stored[section])
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
        }

    def runtime_status(self) -> dict[str, Any]:
        """Return observed task runtime state for the admin controls UI."""
        controls = self.get_controls()
        status: dict[str, Any] = {
            "celery": {
                "configured_enabled": controls.celery.enabled,
                "status": "unknown",
                "workers_online": 0,
                "worker_names": [],
                "active_count": 0,
                "reserved_count": 0,
                "scheduled_count": 0,
                "registered_task_count": 0,
                "beat_schedule_count": 0,
                "queue_names": [],
                "error": None,
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

            inspect = celery_app.control.inspect(timeout=0.5)
            stats = inspect.stats() or {}
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            scheduled = inspect.scheduled() or {}
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
            status["celery"].update(
                {
                    "status": "online" if stats else "offline",
                    "workers_online": len(stats),
                    "worker_names": sorted(stats),
                    "active_count": sum(len(tasks or []) for tasks in active.values()),
                    "reserved_count": sum(len(tasks or []) for tasks in reserved.values()),
                    "scheduled_count": sum(len(tasks or []) for tasks in scheduled.values()),
                    "registered_task_count": len(
                        {task for tasks in registered.values() for task in (tasks or [])}
                    ),
                    "beat_schedule_count": len(celery_app.conf.beat_schedule or {}),
                    "queue_names": sorted(name for name in queue_names if name),
                }
            )
        except Exception as exc:
            status["celery"].update({"status": "unavailable", "error": str(exc)})
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
        return {
            "status": "ok",
            "audit": self.cleanup_audit_events(),
            "disk_logs": self.cleanup_disk_logs(),
        }
