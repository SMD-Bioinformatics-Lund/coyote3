"""Internal API routes for metadata and ingestion operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.internal import (
    InternalCollectionBulkInsertRequest,
    InternalCollectionInsertPayload,
    InternalCollectionInsertRequest,
    InternalCollectionSupportPayload,
    InternalIngestDependentsPayload,
    InternalIngestDependentsRequest,
    InternalIngestSampleBundlePayload,
    InternalIngestSampleBundleRequest,
    IsglMetaPayload,
    RoleLevelsPayload,
)
from api.core.internal.ports import InternalRepository
from api.deps.repositories import get_internal_repository
from api.extensions import util
from api.security.access import ApiUser, _enforce_access, _require_internal_token, require_access
from api.services.internal_ingest_service import InternalIngestService

router = APIRouter(tags=["internal"])


@router.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(
    request: Request, repository: InternalRepository = Depends(get_internal_repository)
):
    """Return role levels internal.

    Args:
        request (Request): Value for ``request``.
        repository (InternalRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _require_internal_token(request)
    role_levels = {
        role.get("role_id"): role.get("level", 0)
        for role in repository.get_all_roles()
        if role.get("role_id")
    }
    return util.common.convert_to_serializable({"status": "ok", "role_levels": role_levels})


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    repository: InternalRepository = Depends(get_internal_repository),
):
    """Return isgl meta internal.

    Args:
        isgl_id (str): Value for ``isgl_id``.
        request (Request): Value for ``request``.
        repository (InternalRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(repository.is_isgl_adhoc(isgl_id)),
            "display_name": repository.get_isgl_display_name(isgl_id),
        }
    )


@router.post(
    "/api/v1/internal/ingest/dependents",
    response_model=InternalIngestDependentsPayload,
)
def ingest_dependents_internal(
    payload: InternalIngestDependentsRequest,
    _user: ApiUser = Depends(require_access(min_role="admin")),
):
    """Write parsed dependent ingestion payload into Mongo collections."""

    written = InternalIngestService.ingest_dependents(
        sample_id=str(payload.sample_id),
        sample_name=str(payload.sample_name),
        delete_existing=payload.delete_existing,
        preload=payload.preload,
    )

    return util.common.convert_to_serializable(
        {"status": "ok", "sample_id": str(payload.sample_id), "written": written}
    )


@router.post(
    "/api/v1/internal/ingest/sample-bundle",
    response_model=InternalIngestSampleBundlePayload,
)
def ingest_sample_bundle_internal(
    payload: InternalIngestSampleBundleRequest,
    user: ApiUser = Depends(require_access(min_role="admin")),
):
    """Create a fresh sample and all dependent analysis documents atomically."""
    if not payload.spec and not payload.yaml_content:
        raise ValueError("Provide either `spec` or `yaml_content`")
    if payload.spec and payload.yaml_content:
        raise ValueError("Provide only one of `spec` or `yaml_content`")

    source_payload = (
        InternalIngestService.parse_yaml_payload(payload.yaml_content)
        if payload.yaml_content
        else payload.spec.model_dump(exclude_none=True)
    )
    if payload.update_existing:
        _enforce_access(user, permission="edit_sample")
    result = InternalIngestService.ingest_sample_bundle(
        source_payload,
        allow_update=payload.update_existing,
    )
    return util.common.convert_to_serializable(result)


@router.post(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_document_internal(
    payload: InternalCollectionInsertRequest,
    _user: ApiUser = Depends(require_access(min_role="admin")),
):
    """Insert one validated document into a supported collection."""
    result = InternalIngestService.insert_collection_document(
        collection=payload.collection,
        document=payload.document,
        ignore_duplicate=payload.ignore_duplicate,
    )
    return util.common.convert_to_serializable(result)


@router.post(
    "/api/v1/internal/ingest/collection/bulk",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_documents_internal(
    payload: InternalCollectionBulkInsertRequest,
    _user: ApiUser = Depends(require_access(min_role="admin")),
):
    """Insert many validated documents into a supported collection."""
    result = InternalIngestService.insert_collection_documents(
        collection=payload.collection,
        documents=payload.documents,
        ignore_duplicates=payload.ignore_duplicates,
    )
    return util.common.convert_to_serializable(result)


@router.get(
    "/api/v1/internal/ingest/collections",
    response_model=InternalCollectionSupportPayload,
)
def list_supported_ingest_collections_internal(
    _user: ApiUser = Depends(require_access(min_role="admin")),
):
    """List supported collection names for validated collection-ingest endpoints."""
    return util.common.convert_to_serializable(
        {"status": "ok", "collections": InternalIngestService.list_supported_collections()}
    )
