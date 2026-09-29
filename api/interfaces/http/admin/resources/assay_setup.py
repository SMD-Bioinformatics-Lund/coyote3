"""Draft-first assay setup endpoints with independent publication review."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from api.app.container import util
from api.app.deps.services import get_assay_setup_service
from api.application.resources.assay_setup import AssaySetupService
from api.contracts.schemas.assay_setup import (
    AssaySetupAction,
    AssaySetupContent,
    AssaySetupContextPayload,
    AssaySetupDoc,
    AssaySetupListPayload,
    AssaySetupUpdate,
)
from api.interfaces.http.admin.resources.audit import set_managed_resource_audit_context
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

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


@router.get("", response_model=AssaySetupListPayload)
def list_setups(
    user: ApiUser = Depends(require_access(permission="assay.panel:list")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """List saved setup summaries; requires assay.panel:list."""
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/context", response_model=AssaySetupContextPayload)
def new_setup_context(
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Return the assay form and optional scope choices for a new setup."""
    return util.common.convert_to_serializable(service.context(None, actor=user.username))


@router.get("/{identifier}/context", response_model=AssaySetupContextPayload)
def setup_context(
    identifier: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Inspect staged configuration, readiness and revision history without writing data."""
    return util.common.convert_to_serializable(service.context(identifier, actor=user.username))


@router.post("", status_code=201, dependencies=write_dependencies, response_model=AssaySetupDoc)
def create_setup(
    request: Request,
    payload: AssaySetupContent,
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Reserve an assay identifier and save a draft without creating an active ASP."""
    return _response(request, service.save(payload, actor=user.username), "created")


@router.put("/{identifier}", dependencies=write_dependencies, response_model=AssaySetupDoc)
def save_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Save the current draft revision; submitted and published setups are immutable."""
    return _response(
        request,
        service.save(
            payload.content, identifier=identifier, revision=payload.revision, actor=user.username
        ),
        "updated",
    )


@router.post("/{identifier}/submit", dependencies=write_dependencies, response_model=AssaySetupDoc)
def submit_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Validate every selected scope/environment and freeze the setup for review."""
    return _response(
        request,
        service.transition(identifier, payload.revision, "submit", actor=user.username),
        "submitted",
    )


@router.post("/{identifier}/publish", dependencies=write_dependencies, response_model=AssaySetupDoc)
def publish_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Independently approve and atomically activate a complete submitted setup."""
    return _response(
        request,
        service.transition(
            identifier, payload.revision, "publish", actor=user.username, reason=payload.reason
        ),
        "published",
    )


@router.post("/{identifier}/return", response_model=AssaySetupDoc)
def return_setup(
    request: Request,
    identifier: str,
    payload: AssaySetupAction,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssaySetupService = Depends(get_assay_setup_service),
) -> dict[str, Any]:
    """Return a submitted setup to draft with an independent reviewer's explanation."""
    return _response(
        request,
        service.transition(
            identifier, payload.revision, "return", actor=user.username, reason=payload.reason
        ),
        "returned",
    )
