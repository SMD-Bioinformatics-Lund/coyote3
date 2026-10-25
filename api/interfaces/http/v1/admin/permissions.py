"""Admin permission management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.app.container import util
from api.app.deps.application import get_permissions
from api.interfaces.http.tags import TAG_ADMIN_ACCESS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import Permissions
from coyote3.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminPermissionContextPayload,
    AdminPermissionCreateContextPayload,
    AdminPermissionsListPayload,
)

router = APIRouter(tags=[TAG_ADMIN_ACCESS])


@router.post(
    "/api/v1/permissions",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create permission policy",
)
def create_permission(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="permission.policy:create")),
    service: Permissions = Depends(get_permissions),
):
    """Create a permission policy."""
    return service.create_permission(payload=payload)


@router.get("/api/v1/permissions", response_model=AdminPermissionsListPayload)
def list_permissions_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="permission.policy:list")),
    service: Permissions = Depends(get_permissions),
):
    """Return the admin permission-policy list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_permissions(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/permissions/create_context", response_model=AdminPermissionCreateContextPayload
)
def create_permission_context_read(
    user: ApiUser = Depends(require_access(permission="permission.policy:create")),
    service: Permissions = Depends(get_permissions),
):
    """Return create-form context for a permission policy."""
    return util.common.convert_to_serializable(service.create_permission_context())


@router.get("/api/v1/permissions/{perm_id}/context", response_model=AdminPermissionContextPayload)
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="permission.policy:view")),
    service: Permissions = Depends(get_permissions),
):
    """Return edit-form context for a permission policy."""
    _ = user
    return util.common.convert_to_serializable(service.permission_context(perm_id=perm_id))


@router.put(
    "/api/v1/permissions/{perm_id}",
    response_model=AdminChangePayload,
    summary="Update permission policy",
)
def update_permission(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="permission.policy:edit")),
    service: Permissions = Depends(get_permissions),
):
    """Update a permission policy."""
    return service.update_permission(perm_id=perm_id, payload=payload)


@router.patch(
    "/api/v1/permissions/{perm_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle permission policy active status",
)
def toggle_permission_status(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="permission.policy:edit")),
    service: Permissions = Depends(get_permissions),
):
    """Toggle a permission policy's active status."""
    _ = user
    return service.toggle_permission_status(perm_id=perm_id)


@router.delete(
    "/api/v1/permissions/{perm_id}",
    response_model=AdminChangePayload,
    summary="Delete permission policy",
)
def delete_permission(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="permission.policy:delete")),
    service: Permissions = Depends(get_permissions),
):
    """Delete a permission policy."""
    _ = user
    return service.delete_permission(perm_id=perm_id)


@router.post("/api/v1/permissions/validate_permission_id", response_model=AdminExistsPayload)
def validate_permission_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="permission.policy:create")),
    service: Permissions = Depends(get_permissions),
):
    """Validate whether a permission_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.validate_permission_id(payload=payload)}
    )


__all__ = [
    "create_permission_context_read",
    "create_permission",
    "delete_permission",
    "list_permissions_read",
    "permission_context_read",
    "toggle_permission_status",
    "update_permission",
    "validate_permission_id_change",
]
