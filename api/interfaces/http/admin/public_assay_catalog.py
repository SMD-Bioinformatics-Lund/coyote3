"""Permission-scoped catalog authoring and publication routes."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from api.app.container import util
from api.app.deps.services import get_admin_public_assay_catalog_service
from api.application.resources.public_assay_catalog import PublicAssayCatalogManagementService
from api.contracts.public import (
    PublicAssayCatalogAdminPayload,
    PublicAssayCatalogMatrixPayload,
    PublicAssayCatalogPayload,
    PublicAssayCatalogRevisionsPayload,
)
from api.contracts.public import (
    PublicAssayCatalogImportRequest as DraftImport,
)
from api.contracts.public import (
    PublicAssayCatalogTransitionRequest as Transition,
)
from api.contracts.public import (
    PublicAssayCatalogUpdateRequest as DraftUpdate,
)
from api.contracts.schemas.public_catalog import PublicAssayCatalogVersionDoc
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

router = APIRouter(prefix="/api/v1/admin/assay-catalog", tags=[TAG_ADMIN_ASSAYS])


def _result(request: Request, document: dict[str, Any], action: str):
    request.state.audit_resource = {
        "type": "public_assay_catalog_version",
        "id": str(document["_id"]),
        "name": document["catalog"]["header"],
        "retention_class": "traceability",
        "message": f"Catalog {action}",
        "metadata": {
            "revision": document["revision"],
            "status": document["status"],
            "version": document.get("content_version"),
        },
    }
    return util.common.convert_to_serializable(document)


@router.get("", response_model=PublicAssayCatalogAdminPayload)
def workspace(
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return util.common.convert_to_serializable(service.workspace())


@router.get("/versions/{oid}", response_model=PublicAssayCatalogVersionDoc)
def version(
    oid: str,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return util.common.convert_to_serializable(service.document(oid))


@router.get("/versions/{oid}/revisions", response_model=PublicAssayCatalogRevisionsPayload)
def revisions(
    oid: str,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return util.common.convert_to_serializable(service.revisions(oid))


@router.post("/preview", response_model=PublicAssayCatalogPayload)
def preview(
    payload: DraftImport,
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return util.common.convert_to_serializable(
        service.preview(payload.document, actor=user.username, mod=mod, cat=cat, isgl_key=isgl_key)
    )


@router.post("/preview/matrix", response_model=PublicAssayCatalogMatrixPayload)
def preview_matrix(
    payload: DraftImport,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    gene: str | None = None,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return util.common.convert_to_serializable(
        service.preview_matrix(
            payload.document,
            actor=user.username,
            page=page,
            per_page=per_page,
            gene=gene,
        )
    )


@router.post("/drafts", status_code=201, response_model=PublicAssayCatalogVersionDoc)
def create(
    request: Request,
    user: ApiUser = Depends(require_access(permission="catalog:draft")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(request, service.create(actor=user.username), "draft created")


@router.post("/imports", status_code=201, response_model=PublicAssayCatalogVersionDoc)
def import_draft(
    request: Request,
    payload: DraftImport,
    user: ApiUser = Depends(require_access(permission="catalog:draft")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(
        request, service.create(actor=user.username, imported=payload.document), "draft imported"
    )


@router.patch("/drafts/{oid}", response_model=PublicAssayCatalogVersionDoc)
def update(
    request: Request,
    oid: str,
    payload: DraftUpdate,
    user: ApiUser = Depends(require_access(permission="catalog:draft")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(
        request,
        service.update(oid, payload.revision, payload.catalog, actor=user.username),
        "draft saved",
    )


@router.post("/drafts/{oid}/submit", response_model=PublicAssayCatalogVersionDoc)
def submit(
    request: Request,
    oid: str,
    payload: Transition,
    user: ApiUser = Depends(require_access(permission="catalog:submit")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(
        request,
        service.submit(oid, payload.revision, payload.assignee, actor=user.username),
        "submitted",
    )


@router.post("/drafts/{oid}/review", response_model=PublicAssayCatalogVersionDoc)
def review(
    request: Request,
    oid: str,
    payload: Transition,
    user: ApiUser = Depends(require_access(permission="catalog:review")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(
        request,
        service.decide(
            oid,
            payload.revision,
            actor=user.username,
            approve=payload.approve,
            publisher=payload.assignee,
            reason=payload.reason,
        ),
        "reviewed",
    )


@router.post("/drafts/{oid}/publish", response_model=PublicAssayCatalogVersionDoc)
def publish(
    request: Request,
    oid: str,
    payload: Transition,
    user: ApiUser = Depends(require_access(permission="catalog:publish")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    return _result(
        request, service.publish(oid, payload.revision, actor=user.username), "published"
    )
