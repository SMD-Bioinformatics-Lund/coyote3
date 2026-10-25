"""Admin user management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.app.container import util
from api.app.deps.application import get_users
from api.interfaces.http.tags import TAG_ADMIN_USERS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import Users
from coyote3.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminUserContextPayload,
    AdminUserCreateContextPayload,
    AdminUsersListPayload,
)

router = APIRouter(tags=[TAG_ADMIN_USERS])


@router.get("/api/v1/users", response_model=AdminUsersListPayload)
def list_users_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="user:list")),
    service: Users = Depends(get_users),
):
    """Return the admin user list."""
    _ = user
    return util.common.convert_to_serializable(
        service.list_users(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/users/create_context", response_model=AdminUserCreateContextPayload)
def create_user_context_read(
    user: ApiUser = Depends(require_access(permission="user:create")),
    service: Users = Depends(get_users),
):
    """Return create-form context for an admin user."""
    return util.common.convert_to_serializable(service.create_user_context())


@router.get("/api/v1/users/{user_id}/context", response_model=AdminUserContextPayload)
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="user:view")),
    service: Users = Depends(get_users),
):
    """Return edit-form context for an admin user."""
    _ = user
    return util.common.convert_to_serializable(service.user_context(user_id=user_id))


@router.post(
    "/api/v1/users", response_model=AdminChangePayload, status_code=201, summary="Create user"
)
def create_user(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="user:create")),
    service: Users = Depends(get_users),
):
    """Create an admin user."""
    return util.common.convert_to_serializable(service.create_user(payload=payload))


@router.put("/api/v1/users/{user_id}", response_model=AdminChangePayload, summary="Update user")
def update_user(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="user:edit")),
    service: Users = Depends(get_users),
):
    """Update an admin user."""
    return util.common.convert_to_serializable(
        service.update_user(user_id=user_id, payload=payload)
    )


@router.delete("/api/v1/users/{user_id}", response_model=AdminChangePayload, summary="Delete user")
def delete_user(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="user:delete")),
    service: Users = Depends(get_users),
):
    """Delete an admin user."""
    return util.common.convert_to_serializable(service.delete_user(user_id=user_id))


@router.patch(
    "/api/v1/users/{user_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle user active status",
)
def toggle_user_status(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="user:edit")),
    service: Users = Depends(get_users),
):
    """Toggle an admin user's active status."""
    return util.common.convert_to_serializable(service.toggle_user_status(user_id=user_id))


@router.post(
    "/api/v1/users/{user_id}/invite",
    response_model=AdminChangePayload,
    summary="Send local user invite",
)
def invite_local_user(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="user:edit")),
    service: Users = Depends(get_users),
):
    """Issue a set-password invite link for local users."""
    return util.common.convert_to_serializable(service.invite_local_user(user_id=user_id))


@router.post("/api/v1/users/validate_username", response_model=AdminExistsPayload)
def validate_username_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="user:create")),
    service: Users = Depends(get_users),
):
    """Validate whether a username is already in use."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.validate_username(payload=payload)}
    )


@router.post("/api/v1/users/validate_email", response_model=AdminExistsPayload)
def validate_email_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="user:create")),
    service: Users = Depends(get_users),
):
    """Validate whether an email address is already in use."""
    _ = user
    return util.common.convert_to_serializable({"exists": service.validate_email(payload=payload)})
