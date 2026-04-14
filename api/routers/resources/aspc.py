"""Configurable assay config router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminAspcContextPayload,
    AdminAspcCreateContextPayload,
    AdminAspcListPayload,
    AdminChangePayload,
    AdminExistsPayload,
)
from api.deps.services import get_admin_aspc_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.resources.aspc import AspcService

router = APIRouter(tags=["resource-aspc"])


@router.get("/api/v1/resources/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="assay.config:list", min_role="user", min_level=9)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Return the assay-config admin list.

    Args:
        user: Authenticated user requesting the list.
        service: Assay-config workflow service.

    Returns:
        dict: Admin list payload for assay configs.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/resources/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    user: ApiUser = Depends(
        require_access(permission="assay.config:create", min_role="manager", min_level=99)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Return create-form context for an assay config.

    Args:
        category: Requested assay category.
        user: Authenticated user requesting create context.
        service: Assay-config workflow service.

    Returns:
        dict: Create-context payload for assay configs.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(category=category, actor_username=user.username)
    )


@router.get("/api/v1/resources/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="assay.config:view", min_role="user", min_level=9)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Return edit-form context for an assay config.

    Args:
        assay_id: Assay-config identifier to load.
        user: Authenticated user requesting edit context.
        service: Assay-config workflow service.

    Returns:
        dict: Edit-context payload for the assay config.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(assay_id=assay_id))


@router.post(
    "/api/v1/resources/aspc",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create assay config",
)
def create_aspc_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="assay.config:create", min_role="manager", min_level=99)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Create an assay config.

    Args:
        payload: Submitted assay-config payload.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    return util.common.convert_to_serializable(
        service.create(payload=payload, actor_username=user.username)
    )


@router.put(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminChangePayload,
    summary="Update assay config",
)
def update_aspc_change(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="assay.config:edit", min_role="manager", min_level=99)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Update an assay config.

    Args:
        assay_id: Assay-config identifier to update.
        payload: Submitted assay-config payload.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    return util.common.convert_to_serializable(
        service.update(assay_id=assay_id, payload=payload, actor_username=user.username)
    )


@router.patch(
    "/api/v1/resources/aspc/{assay_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle assay config status",
)
def toggle_aspc_change(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="assay.config:edit", min_role="manager", min_level=99)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Toggle assay-config active status.

    Args:
        assay_id: Assay-config identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    return util.common.convert_to_serializable(service.toggle(assay_id=assay_id))


@router.delete(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminChangePayload,
    summary="Delete assay config",
)
def delete_aspc_change(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="assay.config:delete", min_role="admin", min_level=99999)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Delete an assay config.

    Args:
        assay_id: Assay-config identifier to delete.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(assay_id=assay_id))


@router.post("/api/v1/resources/aspc/validate_aspc_id", response_model=AdminExistsPayload)
def validate_aspc_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="assay.config:create", min_role="manager", min_level=99)
    ),
    service: AspcService = Depends(get_admin_aspc_service),
):
    """Validate whether an aspc_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {
            "exists": service.assay_config_exists(
                aspc_id=str(payload.get("aspc_id", "") or ""),
                assay_name=str(payload.get("assay_name", "") or ""),
                environment=str(payload.get("environment", "") or ""),
            )
        }
    )
