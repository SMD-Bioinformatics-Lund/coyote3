# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authenticated entry point for adding packaged deployment data."""

from fastapi import APIRouter, Depends, Request

from coyote_api.app.deps.application import get_installation
from coyote_api.contracts.deployment_data import (
    DeploymentDataRequest,
    DeploymentDataResult,
)
from coyote_api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from coyote_api.security.access import ApiUser, require_access
from coyote_api.services.installation import Installation

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
