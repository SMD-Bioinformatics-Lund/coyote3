"""Authenticated entry point for adding packaged deployment data."""

from fastapi import APIRouter, Depends, Request

from api.app.deps.application import get_installation
from api.contracts.deployment_data import (
    DeploymentDataRequest,
    DeploymentDataResult,
)
from api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from api.security.access import ApiUser, require_access
from api.services.installation import Installation

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.post("/api/v1/admin/installation/data", response_model=DeploymentDataResult)
def install_deployment_data(
    payload: DeploymentDataRequest,
    request: Request,
    user: ApiUser = Depends(require_access()),
    service: Installation = Depends(get_installation),
) -> dict:
    """Install missing packaged catalogs; requires an administrator or superuser session."""
    request.state.audit_resource = {
        "type": "deployment_data",
        "id": ",".join(payload.modules),
        "retention_class": "traceability",
        "message": "Install bundled deployment data",
        "metadata": {"modules": payload.modules, "force": payload.force},
    }
    result = service.deployment(modules=payload.modules, force=payload.force)
    request.state.audit_resource["metadata"]["collections"] = result["collections"]
    return result
