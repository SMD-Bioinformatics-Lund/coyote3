"""Configurable genelist router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminExistsPayload,
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
    AdminMutationPayload,
)
from api.deps.services import get_admin_genelist_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminGenelistService

router = APIRouter(tags=["resource-genelists"])


@router.post(
    "/api/v1/resources/genelists",
    response_model=AdminMutationPayload,
    status_code=201,
    summary="Create genelist",
)
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_isgl", min_role="manager", min_level=99)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Create genelist mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create(payload=payload, actor_username=user.username)
    )


@router.get("/api/v1/resources/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """List genelists read.

    Args:
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/resources/genelists/create_context", response_model=AdminGenelistCreateContextPayload
)
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_isgl", min_role="manager", min_level=99)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Create genelist context read.

    Args:
        schema_id (str | None): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload
)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Genelist context read.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(genelist_id=genelist_id))


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/view_context",
    response_model=AdminGenelistViewContextPayload,
)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Genelist view context read.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        assay (str | None): Value for ``assay``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.view_context_payload(genelist_id=genelist_id, assay=assay)
    )


@router.put(
    "/api/v1/resources/genelists/{genelist_id}",
    response_model=AdminMutationPayload,
    summary="Update genelist",
)
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_isgl", min_role="manager", min_level=99)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Update genelist mutation.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.update(
            genelist_id=genelist_id,
            payload=payload,
            actor_username=user.username,
        )
    )


@router.patch(
    "/api/v1/resources/genelists/{genelist_id}/status",
    response_model=AdminMutationPayload,
    summary="Toggle genelist status",
)
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_isgl", min_role="manager", min_level=99)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Toggle genelist mutation.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(genelist_id=genelist_id))


@router.delete(
    "/api/v1/resources/genelists/{genelist_id}",
    response_model=AdminMutationPayload,
    summary="Delete genelist",
)
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_isgl", min_role="admin", min_level=99999)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Delete genelist mutation.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        user (ApiUser): Value for ``user``.
        service (AdminGenelistService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(genelist_id=genelist_id))


@router.post("/api/v1/resources/genelists/validate_isgl_id", response_model=AdminExistsPayload)
def validate_isgl_id_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_isgl", min_role="manager", min_level=99)
    ),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    """Validate whether an isgl_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.genelist_exists(isgl_id=str(payload.get("isgl_id", "")))}
    )
