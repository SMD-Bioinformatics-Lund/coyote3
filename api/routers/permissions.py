"""Admin permission management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminPermissionContextPayload,
    AdminPermissionCreateContextPayload,
    AdminPermissionsListPayload,
)
from api.deps.services import get_permission_management_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.permission_management_service import PermissionManagementService

router = APIRouter(tags=["admin-permissions"])


def _service() -> PermissionManagementService:
    return get_permission_management_service()


def _create_permission(payload: dict, actor_username: str, service: PermissionManagementService):
    return util.common.convert_to_serializable(
        service.create_permission(payload=payload, actor_username=actor_username)
    )


@router.post("/api/v1/permissions", response_model=AdminMutationPayload, status_code=201, summary="Create permission policy")
def create_permission(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    return _create_permission(payload=payload, actor_username=user.username, service=service)


@router.get("/api/v1/permissions", response_model=AdminPermissionsListPayload)
def list_permissions_read(
    user: ApiUser = Depends(require_access(permission="view_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_permissions_payload())


@router.get("/api/v1/permissions/create_context", response_model=AdminPermissionCreateContextPayload)
def create_permission_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/permissions/{perm_id}/context", response_model=AdminPermissionContextPayload)
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="view_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(permission_id=perm_id))


def _update_permission(permission_id: str, payload: dict, actor_username: str, service: PermissionManagementService):
    return util.common.convert_to_serializable(
        service.update_permission(permission_id=permission_id, payload=payload, actor_username=actor_username)
    )


@router.put("/api/v1/permissions/{perm_id}", response_model=AdminMutationPayload, summary="Update permission policy")
def update_permission(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    return _update_permission(permission_id=perm_id, payload=payload, actor_username=user.username, service=service)


def _toggle_permission(permission_id: str, service: PermissionManagementService):
    return util.common.convert_to_serializable(service.toggle_permission(permission_id=permission_id))


@router.patch("/api/v1/permissions/{perm_id}/status", response_model=AdminMutationPayload, summary="Toggle permission policy active status")
def toggle_permission_status(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    _ = user
    return _toggle_permission(permission_id=perm_id, service=service)


def _delete_permission(permission_id: str, service: PermissionManagementService):
    return util.common.convert_to_serializable(service.delete_permission(permission_id=permission_id))


@router.delete("/api/v1/permissions/{perm_id}", response_model=AdminMutationPayload, summary="Delete permission policy")
def delete_permission(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="delete_permission_policy", min_role="admin", min_level=99999)),
    service: PermissionManagementService = Depends(get_permission_management_service),
):
    _ = user
    return _delete_permission(permission_id=perm_id, service=service)


__all__ = [
    "_service",
    "create_permission_context_read",
    "create_permission",
    "delete_permission",
    "list_permissions_read",
    "permission_context_read",
    "toggle_permission_status",
    "update_permission",
]
