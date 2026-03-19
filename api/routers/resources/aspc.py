"""Configurable assay config router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminAspcContextPayload,
    AdminAspcCreateContextPayload,
    AdminAspcListPayload,
    AdminMutationPayload,
)
from api.deps.services import get_admin_aspc_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminAspcService

router = APIRouter(tags=["resource-aspc"])


@router.get("/api/v1/resources/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """List aspc read.

    Args:
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/resources/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_aspc", min_role="manager", min_level=99)
    ),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Create aspc context read.

    Args:
        category (str): Value for ``category``.
        schema_id (str | None): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(
            category=category, schema_id=schema_id, actor_username=user.username
        )
    )


@router.get("/api/v1/resources/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Handle aspc context read.

    Args:
        assay_id (str): Value for ``assay_id``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(assay_id=assay_id))


@router.post(
    "/api/v1/resources/aspc",
    response_model=AdminMutationPayload,
    status_code=201,
    summary="Create assay config",
)
def create_aspc_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_aspc", min_role="manager", min_level=99)
    ),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Create aspc mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.put(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminMutationPayload,
    summary="Update assay config",
)
def update_aspc_mutation(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_aspc", min_role="manager", min_level=99)
    ),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Update aspc mutation.

    Args:
        assay_id (str): Value for ``assay_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.update(assay_id=assay_id, payload=payload))


@router.patch(
    "/api/v1/resources/aspc/{assay_id}/status",
    response_model=AdminMutationPayload,
    summary="Toggle assay config status",
)
def toggle_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_aspc", min_role="manager", min_level=99)
    ),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Toggle aspc mutation.

    Args:
        assay_id (str): Value for ``assay_id``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(assay_id=assay_id))


@router.delete(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminMutationPayload,
    summary="Delete assay config",
)
def delete_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_aspc", min_role="admin", min_level=99999)
    ),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    """Delete aspc mutation.

    Args:
        assay_id (str): Value for ``assay_id``.
        user (ApiUser): Value for ``user``.
        service (AdminAspcService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(assay_id=assay_id))
