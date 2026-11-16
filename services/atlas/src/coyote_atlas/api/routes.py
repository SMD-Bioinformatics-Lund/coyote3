# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Plan and install references through the server's existing administrator policy."""

from coyote_api.app.deps.services import get_deployment_data_service
from coyote_api.contracts.deployment_data import DeploymentDataResult
from coyote_api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from coyote_api.security.access import ApiUser, require_access
from coyote_api.services.provisioning.deployment_data import DeploymentDataService
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from coyote_atlas.bundle import ReferenceBundle
from coyote_atlas.models import InstallationPlan

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


class ReferenceApplyRequest(BaseModel):
    """Pin the reviewed package identity without accepting client data or filesystem paths."""

    model_config = ConfigDict(extra="forbid")
    expected_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    force: bool = False


class ReferencePlanResult(BaseModel):
    """A validated package plan and currently empty logical target collections."""

    plan: InstallationPlan
    pending: list[str]


class ReferenceApplyResult(DeploymentDataResult):
    """Collection results and the package identity submitted to the authorized installer."""

    plan: InstallationPlan


@router.get("/api/v1/admin/references/plan", response_model=ReferencePlanResult)
def plan_references(
    user: ApiUser = Depends(require_access()),
    service: DeploymentDataService = Depends(get_deployment_data_service),
) -> dict:
    """Inspect the installed reference bundle and empty targets; requires an administrator.


    Args:
        user: Current session principal subject to host authorization.
        service: Host's deployment-data service bound to configured persistence.

    Returns:
        Validated package identity and read-only target occupancy; this performs no writes.

    Raises:
        AppError: The principal lacks the administrator role or must change their password.
        ValueError: The packaged references fail integrity or contract validation.
    """
    service.authorize(user)
    return {
        "plan": ReferenceBundle.packaged().plan(),
        "pending": service.repository.pending("knowledgebase"),
    }


@router.post("/api/v1/admin/references/apply", response_model=ReferenceApplyResult)
def apply_references(
    payload: ReferenceApplyRequest,
    request: Request,
    user: ApiUser = Depends(require_access()),
    service: DeploymentDataService = Depends(get_deployment_data_service),
) -> dict:
    """Install the reviewed package with existing preservation rules; requires an administrator.

    The manifest hash must match the installed Atlas package. Existing data is
    preserved unless explicit force requests the host's controlled bundled repair.


    Args:
        payload: Reviewed manifest digest and explicit repair choice.
        request: Host request receiving traceability metadata for the mutation audit.
        user: Current session principal; no caller-selected installer identity is accepted.
        service: Existing authorized deployment-data installer.

    Returns:
        Per-collection installation results and validated package identity.

    Raises:
        AppError: Authorization or the existing installation workflow rejects the request.
        HTTPException: The reviewed bundle has changed, producing HTTP 409 without installation.
        ValueError: Packaged integrity or collection contracts are invalid.
    """
    service.authorize(user)
    plan = ReferenceBundle.packaged().plan()
    if payload.expected_manifest_sha256 != plan.manifest_sha256:
        raise HTTPException(409, detail="The reference bundle changed; review a new plan")
    request.state.audit_resource = {
        "type": "deployment_data",
        "id": "knowledgebase",
        "retention_class": "traceability",
        "message": "Install reviewed reference bundle",
        "metadata": {"reference_bundle": plan.model_dump(mode="json"), "force": payload.force},
    }
    result = service.install(user=user, modules=["knowledgebase"], force=payload.force)
    request.state.audit_resource["metadata"]["collections"] = result["collections"]
    return {**result, "plan": plan}
