"""Admin permission management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminPermissionContextPayload,
    AdminPermissionCreateContextPayload,
    AdminPermissionsListPayload,
)
from api.deps.services import get_permission_management_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.accounts.permissions import PermissionManagementService

router = APIRouter(tags=["admin-permissions"])


def _service() -> PermissionManagementService:
    """Return the admin permission workflow service."""
    return get_permission_management_service()


def _create_permission(payload: dict, actor_username: str, service: PermissionManagementService):
    """Create a permission policy and serialize the change response."""
    return util.common.convert_to_serializable(
        service.create_permission(payload=payload, actor_username=actor_username)
    )


@router.post(
    "/api/v1/permissions",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create permission policy",
)
def create_permission(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Create a permission policy."""
    return _create_permission(payload=payload, actor_username=user.username, service=service)


@router.get("/api/v1/permissions", response_model=AdminPermissionsListPayload)
def list_permissions_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Return the admin permission-policy list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_permissions_payload(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/permissions/create_context", response_model=AdminPermissionCreateContextPayload
)
def create_permission_context_read(
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Return create-form context for a permission policy."""
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get("/api/v1/permissions/{perm_id}/context", response_model=AdminPermissionContextPayload)
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Return edit-form context for a permission policy."""
    _ = user
    return util.common.convert_to_serializable(service.context_payload(permission_id=perm_id))


def _update_permission(
    permission_id: str, payload: dict, actor_username: str, service: PermissionManagementService
):
    """Update a permission policy and serialize the change response."""
    return util.common.convert_to_serializable(
        service.update_permission(
            permission_id=permission_id, payload=payload, actor_username=actor_username
        )
    )


@router.put(
    "/api/v1/permissions/{perm_id}",
    response_model=AdminChangePayload,
    summary="Update permission policy",
)
def update_permission(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Update a permission policy."""
    return _update_permission(
        permission_id=perm_id, payload=payload, actor_username=user.username, service=service
    )


def _toggle_permission(permission_id: str, service: PermissionManagementService):
    """Toggle a permission policy and serialize the change response."""
    return util.common.convert_to_serializable(
        service.toggle_permission(permission_id=permission_id)
    )


@router.patch(
    "/api/v1/permissions/{perm_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle permission policy active status",
)
def toggle_permission_status(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Toggle a permission policy's active status."""
    _ = user
    return _toggle_permission(permission_id=perm_id, service=service)


def _delete_permission(permission_id: str, service: PermissionManagementService):
    """Delete a permission policy and serialize the change response."""
    return util.common.convert_to_serializable(
        service.delete_permission(permission_id=permission_id)
    )


@router.delete(
    "/api/v1/permissions/{perm_id}",
    response_model=AdminChangePayload,
    summary="Delete permission policy",
)
def delete_permission(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Delete a permission policy."""
    _ = user
    return _delete_permission(permission_id=perm_id, service=service)


@router.post("/api/v1/permissions/validate_permission_id", response_model=AdminExistsPayload)
def validate_permission_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    """Validate whether a permission_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.permission_exists(permission_id=str(payload.get("permission_id", "")))}
    )


__all__ = [
    "_service",
    "create_permission_context_read",
    "create_permission",
    "delete_permission",
    "list_permissions_read",
    "permission_context_read",
    "toggle_permission_status",
    "update_permission",
    "validate_permission_id_change",
]
