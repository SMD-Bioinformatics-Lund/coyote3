"""Admin role management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminRoleContextPayload,
    AdminRoleCreateContextPayload,
    AdminRolesListPayload,
)
from api.deps.services import get_admin_role_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.accounts.roles import RoleManagementService

router = APIRouter(tags=["admin-roles"])


def _service() -> RoleManagementService:
    """Return the admin role workflow service."""
    return get_admin_role_service()


@router.get("/api/v1/roles", response_model=AdminRolesListPayload)
def list_roles_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="view_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Return the admin role list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_roles_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/roles/create_context", response_model=AdminRoleCreateContextPayload)
def create_role_context_read(
    user: ApiUser = Depends(
        require_access(permission="create_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Return create-form context for a role."""
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get("/api/v1/roles/{role_id}/context", response_model=AdminRoleContextPayload)
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Return edit-form context for a role."""
    _ = user
    return util.common.convert_to_serializable(service.context_payload(role_id=role_id))


def _create_role(payload: dict, actor_username: str, service: RoleManagementService):
    """Create a role and serialize the change response."""
    return util.common.convert_to_serializable(
        service.create_role(payload=payload, actor_username=actor_username)
    )


@router.post(
    "/api/v1/roles", response_model=AdminChangePayload, status_code=201, summary="Create role"
)
def create_role(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Create a role."""
    return _create_role(payload=payload, actor_username=user.username, service=service)


def _update_role(role_id: str, payload: dict, actor_username: str, service: RoleManagementService):
    """Update a role and serialize the change response."""
    return util.common.convert_to_serializable(
        service.update_role(role_id=role_id, payload=payload, actor_username=actor_username)
    )


@router.put("/api/v1/roles/{role_id}", response_model=AdminChangePayload, summary="Update role")
def update_role(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Update a role."""
    return _update_role(
        role_id=role_id, payload=payload, actor_username=user.username, service=service
    )


def _toggle_role(role_id: str, service: RoleManagementService):
    """Toggle a role's active status and serialize the response."""
    return util.common.convert_to_serializable(service.toggle_role(role_id=role_id))


@router.patch(
    "/api/v1/roles/{role_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle role active status",
)
def toggle_role_status(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Toggle a role's active status."""
    _ = user
    return _toggle_role(role_id=role_id, service=service)


def _delete_role(role_id: str, service: RoleManagementService):
    """Delete a role and serialize the change response."""
    return util.common.convert_to_serializable(service.delete_role(role_id=role_id))


@router.delete("/api/v1/roles/{role_id}", response_model=AdminChangePayload, summary="Delete role")
def delete_role(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Delete a role."""
    _ = user
    return _delete_role(role_id=role_id, service=service)


@router.post("/api/v1/roles/validate_role_id", response_model=AdminExistsPayload)
def validate_role_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_role", min_role="admin", min_level=99999)
    ),
    service: RoleManagementService = Depends(get_admin_role_service),
):
    """Validate whether a role_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.role_exists(role_id=str(payload.get("role_id", "")))}
    )


__all__ = [
    "_service",
    "create_role_context_read",
    "create_role",
    "delete_role",
    "list_roles_read",
    "role_context_read",
    "toggle_role_status",
    "update_role",
    "validate_role_id_change",
]
