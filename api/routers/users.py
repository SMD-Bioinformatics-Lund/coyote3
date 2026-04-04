"""Admin user management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminExistsPayload,
    AdminMutationPayload,
    AdminUserContextPayload,
    AdminUserCreateContextPayload,
    AdminUsersListPayload,
)
from api.deps.services import get_admin_user_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.accounts.users import UserManagementService

router = APIRouter(tags=["admin-users"])


def _service() -> UserManagementService:
    """Service.

    Returns:
            The  service result.
    """
    return get_admin_user_service()


@router.get("/api/v1/users", response_model=AdminUsersListPayload)
def list_users_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="view_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """List users read.

    Args:
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_users_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/users/create_context", response_model=AdminUserCreateContextPayload)
def create_user_context_read(
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Create user context read.

    Args:
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get("/api/v1/users/{user_id}/context", response_model=AdminUserContextPayload)
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """User context read.

    Args:
        user_id (str): Value for ``user_id``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(user_id=user_id))


def _create_user(payload: dict, actor_username: str, service: UserManagementService):
    """Create user.

    Args:
            payload: Payload.
            actor_username: Actor username.
            service: Service.

    Returns:
            The  create user result.
    """
    return util.common.convert_to_serializable(
        service.create_user(payload=payload, actor_username=actor_username)
    )


@router.post(
    "/api/v1/users", response_model=AdminMutationPayload, status_code=201, summary="Create user"
)
def create_user(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Create user.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    return _create_user(payload=payload, actor_username=user.username, service=service)


def _update_user(user_id: str, payload: dict, actor_username: str, service: UserManagementService):
    """Update user.

    Args:
            user_id: User id.
            payload: Payload.
            actor_username: Actor username.
            service: Service.

    Returns:
            The  update user result.
    """
    return util.common.convert_to_serializable(
        service.update_user(user_id=user_id, payload=payload, actor_username=actor_username)
    )


@router.put("/api/v1/users/{user_id}", response_model=AdminMutationPayload, summary="Update user")
def update_user(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Update user.

    Args:
        user_id (str): Value for ``user_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    return _update_user(
        user_id=user_id, payload=payload, actor_username=user.username, service=service
    )


def _delete_user(user_id: str, service: UserManagementService):
    """Delete user.

    Args:
            user_id: User id.
            service: Service.

    Returns:
            The  delete user result.
    """
    return util.common.convert_to_serializable(service.delete_user(user_id=user_id))


@router.delete(
    "/api/v1/users/{user_id}", response_model=AdminMutationPayload, summary="Delete user"
)
def delete_user(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Delete user.

    Args:
        user_id (str): Value for ``user_id``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return _delete_user(user_id=user_id, service=service)


def _toggle_user(user_id: str, service: UserManagementService):
    """Toggle user.

    Args:
            user_id: User id.
            service: Service.

    Returns:
            The  toggle user result.
    """
    return util.common.convert_to_serializable(service.toggle_user(user_id=user_id))


@router.patch(
    "/api/v1/users/{user_id}/status",
    response_model=AdminMutationPayload,
    summary="Toggle user active status",
)
def toggle_user_status(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Toggle user status.

    Args:
        user_id (str): Value for ``user_id``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return _toggle_user(user_id=user_id, service=service)


@router.post(
    "/api/v1/users/{user_id}/invite",
    response_model=AdminMutationPayload,
    summary="Send local user invite",
)
def invite_local_user(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Issue a set-password invite link for local users."""
    return util.common.convert_to_serializable(
        service.send_local_user_invite(user_id=user_id, actor_username=user.username)
    )


@router.post("/api/v1/users/validate_username", response_model=AdminExistsPayload)
def validate_username_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Validate username mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.username_exists(username=str(payload.get("username", "")))}
    )


@router.post("/api/v1/users/validate_email", response_model=AdminExistsPayload)
def validate_email_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
    service: UserManagementService = Depends(get_admin_user_service),
):
    """Validate email mutation.

    Args:
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (UserManagementService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.email_exists(email=str(payload.get("email", "")))}
    )


__all__ = [
    "_service",
    "create_user_context_read",
    "create_user",
    "delete_user",
    "list_users_read",
    "toggle_user_status",
    "invite_local_user",
    "update_user",
    "user_context_read",
    "validate_email_mutation",
    "validate_username_mutation",
]
