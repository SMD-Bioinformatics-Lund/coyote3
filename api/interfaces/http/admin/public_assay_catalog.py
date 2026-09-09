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
    """Attach catalog audit metadata and serialize the changed version.

    Args:
        request: Request whose state receives the audit resource descriptor.
        document: Saved version with ID, catalog header, revision, and status.
        action: Completed action text appended to the audit message.

    Returns:
        The version converted by the shared response serializer.

    Notes:
        Replaces request.state.audit_resource with traceability metadata.
    """
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
    """Read the catalog authoring workspace; requires `catalog:view`.

    \u000c

    Args:
        user: User authorized by the view dependency.
        service: Catalog management service supplying workspace data.

    Returns:
        Serialized catalog, versions, source choices, eligible reviewers and
        publishers, and authoring presets.
    """
    return util.common.convert_to_serializable(service.workspace())


@router.get("/versions/{oid}", response_model=PublicAssayCatalogVersionDoc)
def version(
    oid: str,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    """Read one catalog version; requires `catalog:view`.

    \u000c

    Args:
        oid: Catalog version document identifier.
        user: User authorized by the view dependency.
        service: Catalog management service used to retrieve the version.

    Returns:
        The serialized catalog version document.

    Raises:
        AppError: If the version does not exist (404).
    """
    return util.common.convert_to_serializable(service.document(oid))


@router.get("/versions/{oid}/revisions", response_model=PublicAssayCatalogRevisionsPayload)
def revisions(
    oid: str,
    user: ApiUser = Depends(require_access(permission="catalog:view")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    """Read a catalog version's revision history; requires `catalog:view`.

    \u000c

    Args:
        oid: Catalog version document identifier.
        user: User authorized by the view dependency.
        service: Catalog management service used to retrieve history.

    Returns:
        A serialized items envelope containing saved revisions.

    Raises:
        AppError: If the version does not exist (404).
    """
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
    """Render supplied catalog content without saving it; requires `catalog:view`.

    \u000c

    Args:
        payload: Catalog document to validate and render.
        mod: Optional modality selection; None leaves it unselected.
        cat: Optional category selection within the modality.
        isgl_key: Optional gene-list selection for the category.
        user: Authorized user attributed during content preparation.
        service: Catalog management service using the public catalog renderer.

    Returns:
        Serialized catalog context for the requested selections.

    Raises:
        AppError: If content validation fails (422) or the renderer cannot
            resolve the catalog or requested selection (404).
    """
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
    """Preview a catalog's gene matrix without saving it; requires `catalog:view`.

    \u000c

    Args:
        payload: Catalog document to validate and render.
        page: One-based matrix page; defaults to 1.
        per_page: Rows per page from 1 to 500; defaults to 100.
        gene: Optional gene search text; None omits gene filtering.
        user: Authorized user attributed during content preparation.
        service: Catalog management service using the public matrix renderer.

    Returns:
        Serialized assay columns, gene rows, and matrix pagination metadata.

    Raises:
        AppError: If the supplied catalog content is invalid (422).
    """
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
    """Create a catalog draft from current content; requires `catalog:draft`.

    \u000c

    Args:
        request: Request receiving audit metadata for the new draft.
        user: Authorized user recorded as the draft creator and content editor.
        service: Catalog management service creating the draft.

    Returns:
        The serialized new draft version, served with HTTP 201.

    Raises:
        AppError: If the source catalog content fails validation (422).

    Notes:
        Uses the published catalog when present, otherwise the service's initial
        document. Does not publish the draft.
    """
    return _result(request, service.create(actor=user.username), "draft created")


@router.post("/imports", status_code=201, response_model=PublicAssayCatalogVersionDoc)
def import_draft(
    request: Request,
    payload: DraftImport,
    user: ApiUser = Depends(require_access(permission="catalog:draft")),
    service: PublicAssayCatalogManagementService = Depends(get_admin_public_assay_catalog_service),
):
    """Import catalog content as a new draft; requires `catalog:draft`.

    \u000c

    Args:
        request: Request receiving audit metadata for the imported draft.
        payload: Full catalog document or supported modality export envelope.
        user: Authorized user recorded as the creator and content editor.
        service: Catalog management service validating and importing content.

    Returns:
        The serialized imported draft version, served with HTTP 201.

    Raises:
        AppError: If the modality export or catalog content is invalid (422).

    Notes:
        A modality export is merged into current catalog content. The resulting
        draft is persisted but not published.
    """
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
    """Replace draft catalog content at a revision; requires `catalog:draft`.

    \u000c

    Args:
        request: Request receiving audit metadata for the saved draft.
        oid: Draft version document identifier.
        payload: Expected revision and replacement catalog content.
        user: Authorized user added to the version's content editors.
        service: Catalog management service validating and saving the draft.

    Returns:
        The serialized draft with an incremented revision.

    Raises:
        AppError: If the version is absent (404), content is invalid (422), or
            draft status or revision conflicts with the update (409).
    """
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
    """Submit a catalog draft to an independent reviewer; requires `catalog:submit`.

    \u000c

    Args:
        request: Request receiving audit metadata for submission.
        oid: Draft version document identifier.
        payload: Expected revision and reviewer username in assignee.
        user: Authorized user recorded as the submitter.
        service: Catalog management service checking links and assigning review.

    Returns:
        The serialized submitted version with an incremented revision.

    Raises:
        AppError: If the version is absent (404), catalog links are invalid
            (422), or state, revision, or reviewer eligibility conflicts (409).

    Notes:
        The service notifies the reviewer when a notification service is available.
    """
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
    """Approve or reject an assigned catalog review; requires `catalog:review`.

    \u000c

    Args:
        request: Request receiving audit metadata for the decision.
        oid: Submitted catalog version document identifier.
        payload: Expected revision, approval flag, reason, and publisher assignee.
        user: Authorized user who must be the assigned independent reviewer.
        service: Catalog management service recording the review decision.

    Returns:
        The serialized approved or rejected version with an incremented revision.

    Raises:
        AppError: If the version is absent (404), another reviewer is assigned
            (403), rejection lacks a reason (422), or state, revision, or
            reviewer/publisher eligibility conflicts (409).

    Notes:
        The service notifies the creator and, on approval, the chosen publisher
        when a notification service is available.
    """
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
    """Publish an approved catalog version; requires `catalog:publish`.

    \u000c

    Args:
        request: Request receiving audit metadata for publication.
        oid: Approved catalog version document identifier.
        payload: Expected revision; other transition fields are not used here.
        user: Authorized user who must be the assigned independent publisher.
        service: Catalog management service validating links and publishing.

    Returns:
        The serialized published version with an incremented revision.

    Raises:
        AppError: If the version is absent (404), another publisher is assigned
            (403), catalog links are invalid (422), or state, revision,
            publication base, or reviewer/publisher eligibility conflicts (409).

    Notes:
        Publication updates the public catalog and notifies the creator when a
        notification service is available.
    """
    return _result(
        request, service.publish(oid, payload.revision, actor=user.username), "published"
    )
