"""Draft-first assay setup endpoints with independent publication review."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_assay_setups
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.interfaces.http.v1.admin.resources.audit import set_managed_resource_audit_context
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import AssaySetups
from coyote3.contracts.schemas.assay_setup import (
    AssaySetupAction,
    AssaySetupContent,
    AssaySetupContextPayload,
    AssaySetupDoc,
    AssaySetupListPayload,
    AssaySetupUpdate,
)

router = APIRouter(prefix="/api/v1/admin/assay-setups", tags=[TAG_ADMIN_ASSAYS])
write_dependencies = [
    Depends(require_access(permission=p))
    for p in ("assay.panel:create", "assay.config:create", "gene_list.insilico:create")
]


def _response(request: Request, doc: dict, action: str) -> dict:
    """Attach traceability metadata and serialize a saved setup document."""
    set_managed_resource_audit_context(
        request,
        resource_type="assay_setup",
        action=action,
        result={
            "resource_id": str(doc["_id"]),
            "meta": {"revision": {"new_version": doc["revision"], "asp_id": doc["asp_id"]}},
        },
    )
    return util.common.convert_to_serializable(doc)


@router.delete("/{identifier}", response_model=AssaySetupDoc)
def delete_setup(
    request: Request,
    identifier: str,
    revision: int = Query(ge=1),
    user: ApiUser = Depends(require_access(permission="assay.panel:delete")),
    service: AssaySetups = Depends(get_assay_setups),
):
    """Delete an unchanged draft or submitted setup; requires assay.panel:delete.

    Published setups and operational assay records are preserved.
    """
    return _response(
        request, service.delete_setup(identifier=identifier, revision=revision), "deleted"
    )


@router.get("", response_model=AssaySetupListPayload)
def list_setups(
    user: ApiUser = Depends(require_access(permission="assay.panel:list")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """List saved setup summaries; requires assay.panel:list."""
    return util.common.convert_to_serializable(service.list_setups())


@router.get("/context", response_model=AssaySetupContextPayload)
def new_setup_context(
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Return the assay form and optional scope choices for a new setup."""
    return util.common.convert_to_serializable(service.new_setup_context())


@router.get("/{identifier}/context", response_model=AssaySetupContextPayload)
def setup_context(
    identifier: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Inspect staged configuration, readiness and revision history without writing data."""
    return util.common.convert_to_serializable(service.setup_context(identifier=identifier))


@router.post("", status_code=201, dependencies=write_dependencies, response_model=AssaySetupDoc)
def create_setup(
    request: Request,
    payload: AssaySetupContent,
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Reserve an assay identifier and save a draft without creating an active ASP."""
    return _response(request, service.create_setup(payload=payload), "created")


@router.put("/{identifier}", dependencies=write_dependencies, response_model=AssaySetupDoc)
def save_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Save the current draft revision; submitted and published setups are immutable."""
    return _response(
        request,
        service.save_setup(identifier=identifier, payload=payload),
        "updated",
    )


@router.post("/{identifier}/submit", dependencies=write_dependencies, response_model=AssaySetupDoc)
def submit_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Validate every selected scope/environment and freeze the setup for review."""
    return _response(
        request,
        service.submit_setup(identifier=identifier, payload=payload),
        "submitted",
    )


@router.post("/{identifier}/publish", dependencies=write_dependencies, response_model=AssaySetupDoc)
def publish_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Independently approve and atomically activate a complete submitted setup."""
    return _response(
        request,
        service.publish_setup(identifier=identifier, payload=payload),
        "published",
    )


@router.post("/{identifier}/return", response_model=AssaySetupDoc)
def return_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetups = Depends(get_assay_setups),
) -> dict[str, Any]:
    """Return a submitted setup to draft with an independent reviewer's explanation."""
    return _response(
        request,
        service.return_setup(identifier=identifier, payload=payload),
        "returned",
    )
