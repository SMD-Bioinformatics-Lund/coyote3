"""Admin role management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.app.container import util
from api.app.deps.application import get_roles
from api.interfaces.http.tags import TAG_ADMIN_ACCESS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import Roles
from coyote3.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminRoleContextPayload,
    AdminRoleCreateContextPayload,
    AdminRolesListPayload,
)

router = APIRouter(tags=[TAG_ADMIN_ACCESS])


@router.get("/api/v1/roles", response_model=AdminRolesListPayload)
def list_roles_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="role:list")),
    service: Roles = Depends(get_roles),
):
    """Return the admin role list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_roles(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/roles/create_context", response_model=AdminRoleCreateContextPayload)
def create_role_context_read(
    user: ApiUser = Depends(require_access(permission="role:create")),
    service: Roles = Depends(get_roles),
):
    """Return create-form context for a role."""
    return util.common.convert_to_serializable(service.create_role_context())


@router.get("/api/v1/roles/{role_id}/context", response_model=AdminRoleContextPayload)
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="role:view")),
    service: Roles = Depends(get_roles),
):
    """Return edit-form context for a role."""
    _ = user
    return util.common.convert_to_serializable(service.role_context(role_id=role_id))


@router.post(
    "/api/v1/roles", response_model=AdminChangePayload, status_code=201, summary="Create role"
)
def create_role(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="role:create")),
    service: Roles = Depends(get_roles),
):
    """Create a role."""
    return service.create_role(payload=payload)


@router.put("/api/v1/roles/{role_id}", response_model=AdminChangePayload, summary="Update role")
def update_role(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="role:edit")),
    service: Roles = Depends(get_roles),
):
    """Update a role."""
    return service.update_role(role_id=role_id, payload=payload)


@router.patch(
    "/api/v1/roles/{role_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle role active status",
)
def toggle_role_status(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="role:edit")),
    service: Roles = Depends(get_roles),
):
    """Toggle a role's active status."""
    _ = user
    return service.toggle_role_status(role_id=role_id)


@router.delete("/api/v1/roles/{role_id}", response_model=AdminChangePayload, summary="Delete role")
def delete_role(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="role:delete")),
    service: Roles = Depends(get_roles),
):
    """Delete a role."""
    _ = user
    return service.delete_role(role_id=role_id)


@router.post("/api/v1/roles/validate_role_id", response_model=AdminExistsPayload)
def validate_role_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="role:create")),
    service: Roles = Depends(get_roles),
):
    """Validate whether a role_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.validate_role_id(payload=payload)}
    )


__all__ = [
    "create_role_context_read",
    "create_role",
    "delete_role",
    "list_roles_read",
    "role_context_read",
    "toggle_role_status",
    "update_role",
    "validate_role_id_change",
]
