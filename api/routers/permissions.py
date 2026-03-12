"""Admin permission management router."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminPermissionContextPayload,
    AdminPermissionCreateContextPayload,
    AdminPermissionsListPayload,
)
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository as MongoAdminRouteRepository
from api.runtime import current_username
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["admin-permissions"])

_admin_repo_instance: MongoAdminRouteRepository | None = None


def _admin_repo() -> MongoAdminRouteRepository:
    global _admin_repo_instance
    if _admin_repo_instance is None:
        _admin_repo_instance = MongoAdminRouteRepository()
    return _admin_repo_instance


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _as_dict_rows(items: list[dict]) -> list[dict]:
    return [dict(item) for item in items if isinstance(item, dict)]


@router.post("/api/v1/admin/permissions/create", response_model=AdminMutationPayload)
def create_permission_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_permission_policy", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active permission schemas found")

    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise api_error(404, "Selected schema not found")

    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    form_data = payload.get("form_data", {})
    policy = util.admin.process_form_to_config(form_data, schema)
    policy.setdefault("is_active", True)
    policy_id = str(policy["permission_name"]).strip()
    policy["permission_id"] = policy_id
    policy["_id"] = policy_id
    policy["schema_name"] = schema.get("schema_id") or schema["_id"]
    policy["schema_version"] = schema["version"]
    policy = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=deepcopy(policy),
        is_new=True,
    )
    _admin_repo().permissions_handler.create_new_policy(policy)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=policy["_id"], action="create")
    )


@router.get("/api/v1/admin/permissions", response_model=AdminPermissionsListPayload)
def list_permissions_read(
    user: ApiUser = Depends(require_access(permission="view_permission_policy", min_role="admin", min_level=99999)),
):
    permission_policies = _as_dict_rows(_admin_repo().permissions_handler.get_all_permissions(is_active=False))
    grouped_permissions: dict[str, list[dict]] = {}
    for policy in permission_policies:
        grouped_permissions.setdefault(policy.get("category", "Uncategorized"), []).append(policy)
    return util.common.convert_to_serializable(
        {"permission_policies": permission_policies, "grouped_permissions": grouped_permissions}
    )


@router.get("/api/v1/admin/permissions/create_context", response_model=AdminPermissionCreateContextPayload)
def create_permission_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_permission_policy", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active permission schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {"schemas": active_schemas, "selected_schema": selected_schema, "schema": schema}
    )


@router.get("/api/v1/admin/permissions/{perm_id}/context", response_model=AdminPermissionContextPayload)
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="view_permission_policy", min_role="admin", min_level=99999)),
):
    permission = _admin_repo().permissions_handler.get_permission(perm_id)
    if not permission:
        raise api_error(404, "Permission policy not found")
    schema = _admin_repo().schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for permission policy")
    return util.common.convert_to_serializable({"permission": permission, "schema": schema})


@router.post("/api/v1/admin/permissions/{perm_id}/update", response_model=AdminMutationPayload)
def update_permission_mutation(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)),
):
    permission = _admin_repo().permissions_handler.get_permission(perm_id)
    if not permission:
        raise api_error(404, "Permission policy not found")
    schema = _admin_repo().schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for permission policy")

    form_data = payload.get("form_data", {})
    updated_permission = util.admin.process_form_to_config(form_data, schema)
    updated_permission["updated_on"] = util.common.utc_now()
    updated_permission["updated_by"] = current_username(default=user.username)
    updated_permission["version"] = permission.get("version", 1) + 1
    updated_permission["schema_name"] = schema.get("schema_id") or schema["_id"]
    updated_permission["permission_id"] = permission.get("permission_id", perm_id)
    updated_permission["_id"] = permission.get("_id")
    updated_permission["schema_version"] = schema["version"]
    updated_permission = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=updated_permission,
        old_config=permission,
        is_new=False,
    )
    _admin_repo().permissions_handler.update_policy(perm_id, updated_permission)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=perm_id, action="update")
    )


@router.post("/api/v1/admin/permissions/{perm_id}/toggle", response_model=AdminMutationPayload)
def toggle_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)),
):
    perm = _admin_repo().permissions_handler.get_permission(perm_id)
    if not perm:
        raise api_error(404, "Permission policy not found")
    new_status = not bool(perm.get("is_active", True))
    _admin_repo().permissions_handler.toggle_policy_active(perm_id, new_status)
    result = _mutation_payload("admin", resource="permission", resource_id=perm_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/permissions/{perm_id}/delete", response_model=AdminMutationPayload)
def delete_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(require_access(permission="delete_permission_policy", min_role="admin", min_level=99999)),
):
    perm = _admin_repo().permissions_handler.get_permission(perm_id)
    if not perm:
        raise api_error(404, "Permission policy not found")
    _admin_repo().permissions_handler.delete_policy(perm_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=perm_id, action="delete")
    )


__all__ = [
    "_admin_repo",
    "_admin_repo_instance",
    "_as_dict_rows",
    "_mutation_payload",
    "create_permission_context_read",
    "create_permission_mutation",
    "delete_permission_mutation",
    "list_permissions_read",
    "permission_context_read",
    "toggle_permission_mutation",
    "update_permission_mutation",
]
