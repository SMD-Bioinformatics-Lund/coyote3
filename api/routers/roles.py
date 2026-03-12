"""Admin role management router."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminMutationPayload,
    AdminRoleContextPayload,
    AdminRoleCreateContextPayload,
    AdminRolesListPayload,
)
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository as MongoAdminRouteRepository
from api.runtime import current_username
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["admin-roles"])

_admin_repo_instance: MongoAdminRouteRepository | None = None


def _admin_repo() -> MongoAdminRouteRepository:
    global _admin_repo_instance
    if _admin_repo_instance is None:
        _admin_repo_instance = MongoAdminRouteRepository()
    return _admin_repo_instance


def _as_dict_rows(items: list[dict]) -> list[dict]:
    return [dict(item) for item in items if isinstance(item, dict)]


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _permission_policy_options() -> list[dict]:
    permission_policies = _admin_repo().permissions_handler.get_all_permissions(is_active=True)
    return [
        {
            "value": p.get("permission_id"),
            "label": p.get("label", p.get("permission_id")),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]


@router.get("/api/v1/admin/roles", response_model=AdminRolesListPayload)
def list_roles_read(
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
):
    roles = _as_dict_rows(_admin_repo().roles_handler.get_all_roles())
    return util.common.convert_to_serializable({"roles": roles})


@router.get("/api/v1/admin/roles/create_context", response_model=AdminRoleCreateContextPayload)
def create_role_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_role",
        schema_category="RBAC_role",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active role schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
        }
    )


@router.get("/api/v1/admin/roles/{role_id}/context", response_model=AdminRoleContextPayload)
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise api_error(404, "Role not found")
    schema = _admin_repo().schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for role")

    schema = deepcopy(schema)
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["permissions"]["default"] = role.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")

    return util.common.convert_to_serializable({"role": role, "schema": schema})


@router.post("/api/v1/admin/roles/create", response_model=AdminMutationPayload)
def create_role_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_role",
        schema_category="RBAC_role",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active role schemas found")
    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise api_error(404, "Selected schema not found")

    form_data = payload.get("form_data", {})
    role = util.admin.process_form_to_config(form_data, schema)
    role.setdefault("is_active", True)
    role_id = str(role.get("name", "")).strip().lower()
    role["role_id"] = role_id
    role["_id"] = role_id
    role["schema_name"] = schema.get("schema_id") or schema["_id"]
    role["schema_version"] = schema["version"]
    role = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=deepcopy(role),
        is_new=True,
    )
    _admin_repo().roles_handler.create_role(role)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role["_id"], action="create")
    )


@router.post("/api/v1/admin/roles/{role_id}/update", response_model=AdminMutationPayload)
def update_role_mutation(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise api_error(404, "Role not found")
    schema = _admin_repo().schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for role")

    form_data = payload.get("form_data", {})
    updated_role = util.admin.process_form_to_config(form_data, schema)
    updated_role["updated_by"] = current_username(default=user.username)
    updated_role["updated_on"] = util.common.utc_now()
    updated_role["schema_name"] = schema.get("schema_id") or schema["_id"]
    updated_role["schema_version"] = schema["version"]
    updated_role["version"] = role.get("version", 1) + 1
    updated_role["role_id"] = role.get("role_id", role_id)
    updated_role["_id"] = role.get("_id")
    updated_role = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=updated_role,
        old_config=role,
        is_new=False,
    )
    _admin_repo().roles_handler.update_role(role_id, updated_role)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role_id, action="update")
    )


@router.post("/api/v1/admin/roles/{role_id}/toggle", response_model=AdminMutationPayload)
def toggle_role_mutation(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise api_error(404, "Role not found")
    new_status = not bool(role.get("is_active"))
    _admin_repo().roles_handler.toggle_role_active(role_id, new_status)
    result = _mutation_payload("admin", resource="role", resource_id=role_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/roles/{role_id}/delete", response_model=AdminMutationPayload)
def delete_role_mutation(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="delete_role", min_role="admin", min_level=99999)),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise api_error(404, "Role not found")
    _admin_repo().roles_handler.delete_role(role_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role_id, action="delete")
    )


__all__ = [
    "_admin_repo",
    "_admin_repo_instance",
    "_as_dict_rows",
    "_mutation_payload",
    "_permission_policy_options",
    "create_role_context_read",
    "create_role_mutation",
    "delete_role_mutation",
    "list_roles_read",
    "role_context_read",
    "toggle_role_mutation",
    "update_role_mutation",
]
