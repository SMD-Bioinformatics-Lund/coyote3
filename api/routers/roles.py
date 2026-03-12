"""Admin role management router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminRoleContextPayload,
    AdminRoleCreateContextPayload,
    AdminRolesListPayload,
)
from api.deps.services import get_admin_role_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_role_service import AdminRoleService

router = APIRouter(tags=["admin-roles"])


def _service() -> AdminRoleService:
    return get_admin_role_service()


@router.get("/api/v1/roles", response_model=AdminRolesListPayload)
def list_roles_read(
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_roles_payload())


@router.get("/api/v1/roles/create_context", response_model=AdminRoleCreateContextPayload)
def create_role_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/roles/{role_id}/context", response_model=AdminRoleContextPayload)
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(role_id=role_id))


def _create_role(payload: dict, actor_username: str, service: AdminRoleService):
    return util.common.convert_to_serializable(
        service.create_role(payload=payload, actor_username=actor_username)
    )


@router.post("/api/v1/roles", response_model=AdminMutationPayload, status_code=201, summary="Create role")
def create_role(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    return _create_role(payload=payload, actor_username=user.username, service=service)


def _update_role(role_id: str, payload: dict, actor_username: str, service: AdminRoleService):
    return util.common.convert_to_serializable(
        service.update_role(role_id=role_id, payload=payload, actor_username=actor_username)
    )


@router.put("/api/v1/roles/{role_id}", response_model=AdminMutationPayload, summary="Update role")
def update_role(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    return _update_role(role_id=role_id, payload=payload, actor_username=user.username, service=service)


def _toggle_role(role_id: str, service: AdminRoleService):
    return util.common.convert_to_serializable(service.toggle_role(role_id=role_id))


@router.patch("/api/v1/roles/{role_id}/status", response_model=AdminMutationPayload, summary="Toggle role active status")
def toggle_role_status(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    _ = user
    return _toggle_role(role_id=role_id, service=service)


def _delete_role(role_id: str, service: AdminRoleService):
    return util.common.convert_to_serializable(service.delete_role(role_id=role_id))


@router.delete("/api/v1/roles/{role_id}", response_model=AdminMutationPayload, summary="Delete role")
def delete_role(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="delete_role", min_role="admin", min_level=99999)),
    service: AdminRoleService = Depends(get_admin_role_service),
):
    _ = user
    return _delete_role(role_id=role_id, service=service)


__all__ = [
    "_service",
    "create_role_context_read",
    "create_role",
    "delete_role",
    "list_roles_read",
    "role_context_read",
    "toggle_role_status",
    "update_role",
]
