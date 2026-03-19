"""Configurable assay panel router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
)
from api.deps.services import get_admin_panel_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminPanelService

router = APIRouter(tags=["resource-asp"])


@router.post(
    "/api/v1/resources/asp",
    response_model=AdminMutationPayload,
    status_code=201,
    summary="Create assay panel",
)
def create_asp_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Create asp mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.get("/api/v1/resources/asp", response_model=AdminPanelsListPayload)
def list_asp_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """List asp read.

    Args:
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/resources/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Create asp context read.

    Args:
        schema_id (str | None): Value for ``schema_id``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get(
    "/api/v1/resources/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload
)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Handle asp context read.

    Args:
        assay_panel_id (str): Value for ``assay_panel_id``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(panel_id=assay_panel_id))


@router.put(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminMutationPayload,
    summary="Update assay panel",
)
def update_asp_mutation(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Update asp mutation.

    Args:
        assay_panel_id (str): Value for ``assay_panel_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.update(panel_id=assay_panel_id, payload=payload)
    )


@router.patch(
    "/api/v1/resources/asp/{assay_panel_id}/status",
    response_model=AdminMutationPayload,
    summary="Toggle assay panel status",
)
def toggle_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Toggle asp mutation.

    Args:
        assay_panel_id (str): Value for ``assay_panel_id``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(panel_id=assay_panel_id))


@router.delete(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminMutationPayload,
    summary="Delete assay panel",
)
def delete_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_asp", min_role="admin", min_level=99999)
    ),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    """Delete asp mutation.

    Args:
        assay_panel_id (str): Value for ``assay_panel_id``.
        user (ApiUser): Value for ``user``.
        service (AdminPanelService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(panel_id=assay_panel_id))
