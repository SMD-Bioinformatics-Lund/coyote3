"""Configurable assay panel router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
)
from api.deps.services import get_admin_panel_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.resources.asp import AspService

router = APIRouter(tags=["resource-asp"])


@router.post(
    "/api/v1/resources/asp",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create assay panel",
)
def create_asp_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Create an assay panel.

    Args:
        payload: Submitted assay-panel payload.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    return util.common.convert_to_serializable(
        service.create(payload=payload, actor_username=user.username)
    )


@router.get("/api/v1/resources/asp", response_model=AdminPanelsListPayload)
def list_asp_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return the assay-panel admin list.

    Args:
        user: Authenticated user requesting the list.
        service: Assay-panel workflow service.

    Returns:
        dict: Admin list payload for assay panels.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/resources/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return create-form context for an assay panel.

    Args:
        user: Authenticated user requesting create context.
        service: Assay-panel workflow service.

    Returns:
        dict: Create-context payload for assay panels.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get(
    "/api/v1/resources/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload
)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return edit-form context for an assay panel.

    Args:
        assay_panel_id: Assay-panel identifier to load.
        user: Authenticated user requesting edit context.
        service: Assay-panel workflow service.

    Returns:
        dict: Edit-context payload for the assay panel.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(panel_id=assay_panel_id))


@router.put(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminChangePayload,
    summary="Update assay panel",
)
def update_asp_change(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Update an assay panel.

    Args:
        assay_panel_id: Assay-panel identifier to update.
        payload: Submitted assay-panel payload.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    return util.common.convert_to_serializable(
        service.update(panel_id=assay_panel_id, payload=payload, actor_username=user.username)
    )


@router.patch(
    "/api/v1/resources/asp/{assay_panel_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle assay panel status",
)
def toggle_asp_change(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Toggle assay-panel active status.

    Args:
        assay_panel_id: Assay-panel identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(panel_id=assay_panel_id))


@router.delete(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminChangePayload,
    summary="Delete assay panel",
)
def delete_asp_change(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_asp", min_role="admin", min_level=99999)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Delete an assay panel.

    Args:
        assay_panel_id: Assay-panel identifier to delete.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(panel_id=assay_panel_id))


@router.post("/api/v1/resources/asp/validate_asp_id", response_model=AdminExistsPayload)
def validate_asp_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
    service: AspService = Depends(get_admin_panel_service),
):
    """Validate whether an asp_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.panel_exists(asp_id=str(payload.get("asp_id", "")))}
    )
