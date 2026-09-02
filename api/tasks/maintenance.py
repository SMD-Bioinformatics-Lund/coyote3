"""Celery tasks for retention and operational maintenance."""

from __future__ import annotations

from typing import Any

from celery.utils.log import get_task_logger
from filelock import FileLock, Timeout

from api.app.deps.services import (
    get_app_controls_service,
    get_dashboard_service,
    get_public_oncokb_refresh_service,
)
from api.celery_app import celery_app
from api.security.access import api_user_from_user_doc
from api.tasks.controls import disabled_result, task_family_enabled
from api.tasks.ingest import _ensure_worker_runtime, _serializable

logger = get_task_logger(__name__)
DASHBOARD_REFRESH_LOCK_PATH = "/tmp/coyote3-dashboard-metrics-refresh.lock"


@celery_app.task(name="api.tasks.maintenance.run_retention_maintenance", bind=True)
def run_retention_maintenance(self) -> dict[str, Any]:
    """Run audit and disk-log retention maintenance."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")
    logger.info("celery_retention_maintenance_started task_id=%s", self.request.id)
    result = get_app_controls_service().run_maintenance()
    logger.info("celery_retention_maintenance_finished task_id=%s", self.request.id)
    return _serializable(result)


@celery_app.task(name="api.tasks.maintenance.refresh_public_oncokb", bind=True)
def refresh_public_oncokb(self) -> dict[str, Any]:
    """Refresh public OncoKB gene collections from the local HGNC catalogue."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")
    logger.info("celery_public_oncokb_refresh_started task_id=%s", self.request.id)
    result = get_public_oncokb_refresh_service().refresh()
    logger.info("celery_public_oncokb_refresh_finished task_id=%s", self.request.id)
    return _serializable(result)


@celery_app.task(name="api.tasks.maintenance.refresh_dashboard_metrics", bind=True)
def refresh_dashboard_metrics(self, username: str | None = None) -> dict[str, Any]:
    """Refresh persisted dashboard snapshots for active users in the background."""
    _ensure_worker_runtime()
    if not task_family_enabled("maintenance"):
        return disabled_result("maintenance")

    lock = FileLock(DASHBOARD_REFRESH_LOCK_PATH)
    try:
        with lock.acquire(timeout=0):
            service = get_dashboard_service()
            user_docs = service.user_repository.get_all_users()
            eligible_user_docs = [
                user_doc
                for user_doc in user_docs
                if user_doc.get("is_active") is not False
                and (
                    not username
                    or str(user_doc.get("username") or user_doc.get("_id") or "") == username
                )
            ]
            shared_payload = service.build_shared_summary_payload() if eligible_user_docs else {}
            refreshed = 0
            skipped = 0
            failures: list[dict[str, str]] = []
            refreshed_scopes: set[str] = set()
            skipped += len(user_docs) - len(eligible_user_docs)
            for user_doc in eligible_user_docs:
                stored_username = str(user_doc.get("username") or user_doc.get("_id") or "")
                try:
                    api_user = api_user_from_user_doc(user_doc)
                    scope_key = service.summary_scope_key(user=api_user)
                    if scope_key in refreshed_scopes:
                        skipped += 1
                        continue
                    service.refresh_summary_payload(user=api_user, shared_payload=shared_payload)
                    refreshed_scopes.add(scope_key)
                    refreshed += 1
                except Exception as exc:  # pragma: no cover - task integration guard
                    logger.exception(
                        "celery_dashboard_metrics_refresh_failed task_id=%s username=%s",
                        self.request.id,
                        stored_username,
                    )
                    failures.append({"username": stored_username, "error": type(exc).__name__})
    except Timeout:
        logger.info("celery_dashboard_metrics_refresh_skipped reason=already_running")
        return {"status": "skipped", "reason": "already_running"}

    result = {
        "status": "completed" if not failures else "completed_with_errors",
        "refreshed": refreshed,
        "skipped": skipped,
        "failures": failures,
    }
    logger.info(
        "celery_dashboard_metrics_refresh_finished task_id=%s refreshed=%s failures=%s",
        self.request.id,
        refreshed,
        len(failures),
    )
    return _serializable(result)
