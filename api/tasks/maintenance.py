"""Celery tasks for retention and operational maintenance."""

from __future__ import annotations

from typing import Any

from celery.utils.log import get_task_logger

from api.app.deps.services import get_app_controls_service, get_public_oncokb_refresh_service
from api.celery_app import celery_app
from api.tasks.controls import disabled_result, task_family_enabled
from api.tasks.ingest import _ensure_worker_runtime, _serializable

logger = get_task_logger(__name__)


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
