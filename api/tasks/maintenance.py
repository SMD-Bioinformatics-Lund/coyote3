"""Celery tasks for retention and operational maintenance."""

from __future__ import annotations

from typing import Any

from celery.utils.log import get_task_logger
from filelock import FileLock, Timeout

from api.app.application_factory import maintenance_executor
from api.celery_app import celery_app
from api.tasks.controls import disabled_result, task_family_enabled
from api.tasks.ingest import _ensure_worker_runtime, _serializable

logger = get_task_logger(__name__)
DASHBOARD_REFRESH_LOCK_PATH = "/tmp/coyote3-dashboard-metrics-refresh.lock"


@celery_app.task(name="api.tasks.maintenance.erase_deleted_sample_reports")
def erase_deleted_sample_reports() -> dict[str, int]:
    """Complete up to 100 report-file erasures authorized by committed sample deletions."""
    _ensure_worker_runtime()
    return maintenance_executor(logger).erase_reports()


@celery_app.task(name="api.tasks.maintenance.finalize_report_artifacts")
def finalize_report_artifacts() -> dict[str, int]:
    """Resume checksum-verified publication of committed report files."""
    _ensure_worker_runtime()
    return maintenance_executor(logger).finalize_reports()


@celery_app.task(name="api.tasks.maintenance.replay_audit_events")
def replay_audit_events() -> dict[str, Any]:
    """Replay audit queues and publish committed activity independently of maintenance controls.

    Returns:
        Audit delivery count and up to 100 activity notifications processed this run.
    """
    _ensure_worker_runtime()
    return maintenance_executor(logger).replay_audit()


@celery_app.task(name="api.tasks.maintenance.deliver_notification_emails")
def deliver_notification_emails() -> dict[str, Any]:
    """Deliver at most ten leased broadcast emails without blocking HTTP requests.

    Returns:
        Counts by terminal outcome, or not_configured when SMTP is unavailable.
    """
    _ensure_worker_runtime()
    return maintenance_executor(logger).deliver_emails()


@celery_app.task(name="api.tasks.maintenance.export_audit_checkpoint")
def export_audit_checkpoint() -> dict[str, Any]:
    """Export verified chain hashes hourly when an archival mount is configured."""
    _ensure_worker_runtime()
    return maintenance_executor(logger).export_audit_checkpoint()


@celery_app.task(name="api.tasks.maintenance.run_retention_maintenance", bind=True)
def run_retention_maintenance(self) -> dict[str, Any]:
    """Run audit and disk-log retention maintenance."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")
    logger.info("celery_retention_maintenance_started task_id=%s", self.request.id)
    result = maintenance_executor(logger).retention()
    logger.info("celery_retention_maintenance_finished task_id=%s", self.request.id)
    return _serializable(result)


@celery_app.task(name="api.tasks.maintenance.refresh_public_oncokb", bind=True)
def refresh_public_oncokb(self) -> dict[str, Any]:
    """Refresh public OncoKB gene collections from the local HGNC catalogue."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")
    logger.info("celery_public_oncokb_refresh_started task_id=%s", self.request.id)
    result = maintenance_executor(logger).refresh_public_oncokb()
    logger.info("celery_public_oncokb_refresh_finished task_id=%s", self.request.id)
    return _serializable(result)


@celery_app.task(name="api.tasks.maintenance.refresh_dashboard_metrics", bind=True)
def refresh_dashboard_metrics(
    self, username: str | None = None, metrics: list[str] | None = None
) -> dict[str, Any]:
    """Refresh independently cached dashboard metrics for active user scopes."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")

    lock = FileLock(DASHBOARD_REFRESH_LOCK_PATH)
    try:
        with lock.acquire(timeout=0):
            result = maintenance_executor(logger).refresh_dashboard(
                username=username, metrics=metrics, task_id=self.request.id
            )
    except Timeout:
        logger.info("celery_dashboard_metrics_refresh_skipped reason=already_running")
        return {"status": "skipped", "reason": "already_running"}

    logger.info(
        "celery_dashboard_metrics_refresh_finished task_id=%s refreshed=%s failures=%s",
        self.request.id,
        result["refreshed"],
        len(result["failures"]),
    )
    return _serializable(result)
