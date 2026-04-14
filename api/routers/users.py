"""Admin user management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminUserContextPayload,
    AdminUserCreateContextPayload,
    AdminUsersListPayload,
)
from api.deps.services import get_admin_user_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.accounts.users import UserManagementService

router = APIRouter(tags=["admin-users"])


@router.get("/api/v1/users", response_model=AdminUsersListPayload)
def list_users_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="user:list", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Return the admin user list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_users_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/users/create_context", response_model=AdminUserCreateContextPayload)
def create_user_context_read(
    user: ApiUser = Depends(
        require_access(permission="user:create", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Return create-form context for an admin user."""
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get("/api/v1/users/{user_id}/context", response_model=AdminUserContextPayload)
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="user:view", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Return edit-form context for an admin user."""
    _ = user
    return util.common.convert_to_serializable(service.context_payload(user_id=user_id))


@router.post(
    "/api/v1/users", response_model=AdminChangePayload, status_code=201, summary="Create user"
)
def create_user(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="user:create", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Create an admin user."""
    return util.common.convert_to_serializable(
        service.create_user(payload=payload, actor_username=user.username)
    )


@router.put("/api/v1/users/{user_id}", response_model=AdminChangePayload, summary="Update user")
def update_user(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="user:edit", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Update an admin user."""
    return util.common.convert_to_serializable(
        service.update_user(user_id=user_id, payload=payload, actor_username=user.username)
    )


@router.delete("/api/v1/users/{user_id}", response_model=AdminChangePayload, summary="Delete user")
def delete_user(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="user:delete", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Delete an admin user."""
    _ = user
    return util.common.convert_to_serializable(service.delete_user(user_id=user_id))


@router.patch(
    "/api/v1/users/{user_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle user active status",
)
def toggle_user_status(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="user:edit", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Toggle an admin user's active status."""
    _ = user
    return util.common.convert_to_serializable(service.toggle_user(user_id=user_id))


@router.post(
    "/api/v1/users/{user_id}/invite",
    response_model=AdminChangePayload,
    summary="Send local user invite",
)
def invite_local_user(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="user:edit", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Issue a set-password invite link for local users."""
    return util.common.convert_to_serializable(
        service.send_local_user_invite(user_id=user_id, actor_username=user.username)
    )


@router.post("/api/v1/users/validate_username", response_model=AdminExistsPayload)
def validate_username_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="user:create", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Validate whether a username is already in use."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.username_exists(username=str(payload.get("username", "")))}
    )


@router.post("/api/v1/users/validate_email", response_model=AdminExistsPayload)
def validate_email_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="user:create", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Validate whether an email address is already in use."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.email_exists(email=str(payload.get("email", "")))}
    )
