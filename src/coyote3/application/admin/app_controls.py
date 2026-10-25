"""Application controls and operational retention settings."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from coyote3.application.admin.ports import AppControlsRepository
from coyote3.application.common.execution_context import current_username
from coyote3.config.application_modules import APPLICATION_MODULES
from coyote3.config.contracts.application import APP_CONTROLS_ID
from coyote3.config.policy import get_audit_retention_days
from coyote3.contracts.schemas.app_controls import AppControlsDoc


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
            "gzip_disk_logs_after_days": int(config.get("LOG_GZIP_AFTER_DAYS", 7) or 7),
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
        curation={
            "tiering": {
                "small_variant_enabled": True,
                "cnv_enabled": False,
                "fusion_enabled": True,
                "translocation_enabled": False,
            }
        },
    )
    return controls


def merge_controls(defaults: AppControlsDoc, stored: dict[str, Any] | None) -> AppControlsDoc:
    """Merge stored control values onto typed defaults."""
    payload = defaults.model_dump(by_alias=True)
    if stored:
        for section in ("celery", "retention", "modules", "email"):
            stored_section = stored.get(section)
            if isinstance(stored_section, dict):
                payload[section].update(
                    {key: value for key, value in stored_section.items() if key in payload[section]}
                )
        stored_curation = stored.get("curation")
        if isinstance(stored_curation, dict):
            stored_tiering = stored_curation.get("tiering")
            if isinstance(stored_tiering, dict):
                payload["curation"]["tiering"].update(
                    {
                        key: value
                        for key, value in stored_tiering.items()
                        if key in payload["curation"]["tiering"]
                    }
                )
        for key in ("created_on", "updated_by", "updated_on"):
            if stored.get(key) is not None:
                payload[key] = stored[key]
    return AppControlsDoc.model_validate(payload)


def effective_audit_retention_days(
    repository: AppControlsRepository, config: dict[str, Any]
) -> int:
    """Return audit retention from controls, falling back to runtime config."""
    defaults = default_app_controls(config)
    try:
        stored = repository.retention_override()
        controls = merge_controls(defaults, stored)
        return controls.retention.audit_events_days
    except Exception:
        return defaults.retention.audit_events_days


class AppControlsService:
    """DB-backed runtime switches for modules, Celery tasks, and retention."""

    def __init__(
        self,
        repository: AppControlsRepository,
        *,
        config: dict[str, Any],
        runtime_inspector: Callable[..., dict[str, Any]],
        log_cleanup: Callable[..., dict[str, Any]],
        audit_service: Any | None = None,
        index_conflicts_provider: Any | None = None,
        erasure_status_provider: Callable[[], dict[str, int]] | None = None,
    ) -> None:
        """Bind runtime controls and audit inspection to their separate databases.

        Args:
            repository: Controls persistence and audit-retention operations.
            config: Runtime defaults and collection/inspection configuration.
            runtime_inspector: Entry-point supplied worker runtime inspector.
            log_cleanup: Entry-point supplied filesystem retention operation.
            audit_service: Optional recorder for administrative control changes.
            index_conflicts_provider: Optional callable supplying index-conflict details.
            erasure_status_provider: Optional reader for deployment-scoped artifact erasure backlog.
        """
        self.repository = repository
        self.runtime_inspector = runtime_inspector
        self.log_cleanup = log_cleanup
        self.config = config
        self.audit_service = audit_service
        self.index_conflicts_provider = index_conflicts_provider
        self.erasure_status_provider = erasure_status_provider

    def get_controls(self) -> AppControlsDoc:
        """Return effective controls with stored overrides applied."""
        defaults = default_app_controls(self.config)
        stored = self.repository.read()
        return merge_controls(defaults, stored)

    def _inspection_timeout_seconds(self) -> float:
        """Return the deployment-configured Celery inspection timeout."""
        try:
            return max(0.1, float(self.config.get("CELERY_INSPECTION_TIMEOUT_SECONDS", 1.5)))
        except (TypeError, ValueError):
            return 1.5

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
                "inspection_timeout_seconds": self._inspection_timeout_seconds(),
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

        if self.erasure_status_provider is not None:
            try:
                status["report_erasure"] = {"status": "available", **self.erasure_status_provider()}
            except Exception:
                status["report_erasure"] = {"status": "unavailable"}

        try:
            status["celery"].update(
                self.runtime_inspector(
                    enabled=controls.celery.enabled, timeout=self._inspection_timeout_seconds()
                )
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
        for section in ("celery", "retention", "modules", "email"):
            if isinstance(payload.get(section), dict):
                incoming[section].update(payload[section])
        if isinstance(payload.get("curation"), dict):
            tiering = payload["curation"].get("tiering")
            if isinstance(tiering, dict):
                incoming["curation"]["tiering"].update(tiering)
        incoming["control_id"] = APP_CONTROLS_ID
        incoming["updated_by"] = getattr(actor, "username", None) or current_username()
        incoming["updated_on"] = datetime.now(timezone.utc)
        validated = AppControlsDoc.model_validate(incoming)
        update_doc = validated.model_dump(by_alias=True, exclude={"id_", "created_on"})
        saved = self.repository.save(update_doc, now=datetime.now(timezone.utc))
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
        controls = self.get_controls()
        return {
            "modules": {
                module.key: {
                    "enabled": bool(getattr(controls.modules, module.control_field)),
                    "label": module.label,
                    "description": module.description,
                }
                for module in APPLICATION_MODULES
            },
            "curation": {
                "tiering": {
                    "small_variant": controls.curation.tiering.small_variant_enabled,
                    "cnv": controls.curation.tiering.cnv_enabled,
                    "fusion": controls.curation.tiering.fusion_enabled,
                    "translocation": controls.curation.tiering.translocation_enabled,
                }
            },
        }

    def cleanup_audit_events(self) -> dict[str, Any]:
        """Delete audit events older than the configured retention horizon."""
        retention_days = self.get_controls().retention.audit_events_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = self.repository.delete_operational_audit_before(cutoff)
        return {
            "retention_days": retention_days,
            "deleted": deleted,
            "cutoff": cutoff,
        }

    def cleanup_disk_logs(self) -> dict[str, Any]:
        """Apply configured log retention through the supplied filesystem adapter."""
        retention = self.get_controls().retention
        return self.log_cleanup(
            log_root=str(self.config.get("LOG_ROOT") or "logs"),
            retention_days=retention.disk_log_days,
            gzip_after_days=retention.gzip_disk_logs_after_days,
        )

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
