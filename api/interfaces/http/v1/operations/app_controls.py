"""Admin application-control routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.deps.application import get_controls
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.system import Controls
from coyote3.contracts.admin import (
    AdminAppControlsPayload,
    AdminAppControlsUpdatePayload,
    AdminMaintenanceRunPayload,
)

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.get("/api/v1/admin/controls", response_model=AdminAppControlsPayload)
def admin_controls_read(
    user: ApiUser = Depends(require_access(permission="app.controls:view")),
    service: Controls = Depends(get_controls),
):
    """Return effective runtime controls for admin review."""
    return service.read()


@router.put("/api/v1/admin/controls", response_model=AdminAppControlsPayload)
def admin_controls_update(
    payload: AdminAppControlsUpdatePayload,
    user: ApiUser = Depends(require_access(permission="app.controls:edit")),
    service: Controls = Depends(get_controls),
):
    """Persist runtime-control overrides."""
    return service.update(payload.controls)


@router.post("/api/v1/admin/controls/maintenance", response_model=AdminMaintenanceRunPayload)
def admin_controls_maintenance_run(
    user: ApiUser = Depends(require_access(permission="app.maintenance:run")),
    service: Controls = Depends(get_controls),
):
    """Queue one explicit maintenance cleanup run."""
    return service.maintenance()


@router.post(
    "/api/v1/admin/controls/knowledgebases/oncokb-public/refresh",
    response_model=AdminMaintenanceRunPayload,
)
def admin_controls_public_oncokb_refresh(
    user: ApiUser = Depends(require_access(permission="app.maintenance:run")),
    service: Controls = Depends(get_controls),
):
    """Queue a complete HGNC-backed refresh of public OncoKB reference records."""
    return service.refresh_public_oncokb()
