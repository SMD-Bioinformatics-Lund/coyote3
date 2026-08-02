"""Admin application-control routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.services import get_app_controls_service
from api.application.admin.app_controls import AppControlsService
from api.contracts.admin import (
    AdminAppControlsPayload,
    AdminAppControlsUpdatePayload,
    AdminMaintenanceRunPayload,
)
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.get("/api/v1/admin/controls", response_model=AdminAppControlsPayload)
def admin_controls_read(
    user: ApiUser = Depends(require_access(permission="app.controls:view")),
    service: AppControlsService = Depends(get_app_controls_service),
):
    """Return effective runtime controls for admin review."""
    _ = user
    return util.common.convert_to_serializable(service.payload())


@router.put("/api/v1/admin/controls", response_model=AdminAppControlsPayload)
def admin_controls_update(
    payload: AdminAppControlsUpdatePayload,
    user: ApiUser = Depends(require_access(permission="app.controls:edit")),
    service: AppControlsService = Depends(get_app_controls_service),
):
    """Persist runtime-control overrides."""
    service.update_controls(payload.controls, actor=user)
    return util.common.convert_to_serializable(service.payload())


@router.post("/api/v1/admin/controls/maintenance", response_model=AdminMaintenanceRunPayload)
def admin_controls_maintenance_run(
    user: ApiUser = Depends(require_access(permission="app.maintenance:run")),
):
    """Queue one explicit maintenance cleanup run."""
    _ = user
    from api.tasks.maintenance import run_retention_maintenance

    result = run_retention_maintenance.delay()
    return {"status": "queued", "task_id": result.id}
