"""Configurable schema router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminSchemaContextPayload,
    AdminSchemasListPayload,
)
from api.deps.services import get_admin_schema_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminSchemaService

router = APIRouter(tags=["resource-schemas"])


@router.post(
    "/api/v1/resources/schemas",
    response_model=AdminMutationPayload,
    status_code=201,
    summary="Create schema",
)
def create_schema_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_schema", min_role="developer", min_level=9999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """Create schema mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create(payload=payload, actor_username=user.username)
    )


@router.get("/api/v1/resources/schemas", response_model=AdminSchemasListPayload)
def list_schemas_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="view_schema", min_role="developer", min_level=9999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """List schemas read.

    Args:
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/resources/schemas/{schema_id}/context", response_model=AdminSchemaContextPayload
)
def schema_context_read(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_schema", min_role="developer", min_level=9999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """Schema context read.

    Args:
        schema_id (str): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(schema_id=schema_id))


@router.put(
    "/api/v1/resources/schemas/{schema_id}",
    response_model=AdminMutationPayload,
    summary="Update schema",
)
def update_schema_mutation(
    schema_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_schema", min_role="developer", min_level=9999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """Update schema mutation.

    Args:
        schema_id (str): Value for ``schema_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.update(schema_id=schema_id, payload=payload, actor_username=user.username)
    )


@router.patch(
    "/api/v1/resources/schemas/{schema_id}/status",
    response_model=AdminMutationPayload,
    summary="Toggle schema status",
)
def toggle_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_schema", min_role="developer", min_level=9999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """Toggle schema mutation.

    Args:
        schema_id (str): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(schema_id=schema_id))


@router.delete(
    "/api/v1/resources/schemas/{schema_id}",
    response_model=AdminMutationPayload,
    summary="Delete schema",
)
def delete_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_schema", min_role="admin", min_level=99999)
    ),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    """Delete schema mutation.

    Args:
        schema_id (str): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminSchemaService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(schema_id=schema_id))
