"""Admin user management router."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminExistsPayload,
    AdminMutationPayload,
    AdminUserContextPayload,
    AdminUserCreateContextPayload,
    AdminUsersListPayload,
)
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository as MongoAdminRouteRepository
from api.runtime import current_username
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["admin-users"])

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


def _role_map() -> dict[str, dict]:
    all_roles = _admin_repo().roles_handler.get_all_roles()
    return {
        role["role_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }
        for role in all_roles
    }


def _assay_group_map() -> dict[str, list[dict]]:
    assay_groups_panels = _admin_repo().asp_handler.get_all_asps()
    return util.common.create_assay_group_map(assay_groups_panels)


def _user_role_permission_map() -> dict[str, dict[str, list[str]]]:
    all_roles = _admin_repo().roles_handler.get_all_roles()
    return {
        role["role_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
        }
        for role in all_roles
    }


@router.get("/api/v1/admin/users", response_model=AdminUsersListPayload)
def list_users_read(
    user: ApiUser = Depends(require_access(permission="view_user", min_role="admin", min_level=99999)),
):
    users = _as_dict_rows(_admin_repo().user_handler.get_all_users())
    roles = _admin_repo().roles_handler.get_role_colors()
    return util.common.convert_to_serializable({"users": users, "roles": roles})


@router.get("/api/v1/admin/users/create_context", response_model=AdminUserCreateContextPayload)
def create_user_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active user schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise api_error(404, "User schema not found")

    schema = deepcopy(selected_schema)
    schema["fields"]["role"]["options"] = _admin_repo().roles_handler.get_all_role_names()
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["assay_groups"]["options"] = _admin_repo().asp_handler.get_all_asp_groups()
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
            "role_map": _role_map(),
            "assay_group_map": _assay_group_map(),
        }
    )


@router.get("/api/v1/admin/users/{user_id}/context", response_model=AdminUserContextPayload)
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="view_user", min_role="admin", min_level=99999)),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise api_error(404, "User not found")

    schema = _admin_repo().schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for user")

    schema = deepcopy(schema)
    schema["fields"]["role"]["options"] = _admin_repo().roles_handler.get_all_role_names()
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["permissions"]["default"] = user_doc.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = user_doc.get("deny_permissions")
    schema["fields"]["assay_groups"]["options"] = _admin_repo().asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["default"] = user_doc.get("assay_groups", [])
    schema["fields"]["assays"]["default"] = user_doc.get("assays", [])

    return util.common.convert_to_serializable(
        {
            "user_doc": user_doc,
            "schema": schema,
            "role_map": _role_map(),
            "assay_group_map": _assay_group_map(),
        }
    )


@router.post("/api/v1/admin/users/create", response_model=AdminMutationPayload)
def create_user_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )
    if not active_schemas:
        raise api_error(400, "No active user schemas found")
    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise api_error(404, "User schema not found")

    role_map = _user_role_permission_map()
    form_data = payload.get("form_data", {})
    role_permissions = role_map.get(form_data.get("role"), {})
    form_data["permissions"] = list(
        set(form_data.get("permissions", [])) - set(role_permissions.get("permissions", []))
    )
    form_data["deny_permissions"] = list(
        set(form_data.get("deny_permissions", [])) - set(role_permissions.get("deny_permissions", []))
    )
    user_data = util.admin.process_form_to_config(form_data, schema)
    user_data.setdefault("is_active", True)
    user_data["_id"] = user_data["username"]
    user_data["user_id"] = user_data["username"]
    user_data["schema_name"] = schema.get("schema_id") or schema["_id"]
    user_data["schema_version"] = schema["version"]
    user_data["email"] = user_data["email"].lower()
    user_data["username"] = user_data["username"].lower()
    if user_data["auth_type"] == "coyote3" and user_data["password"]:
        user_data["password"] = util.common.hash_password(user_data["password"])
    else:
        user_data["password"] = None
    user_data = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=deepcopy(user_data),
        is_new=True,
    )
    _admin_repo().user_handler.create_user(user_data)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_data["username"], action="create")
    )


@router.post("/api/v1/admin/users/{user_id}/update", response_model=AdminMutationPayload)
def update_user_mutation(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_user", min_role="admin", min_level=99999)),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise api_error(404, "User not found")
    schema = _admin_repo().schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise api_error(404, "Schema not found for user")

    role_map = _user_role_permission_map()
    form_data = payload.get("form_data", {})
    updated_user = util.admin.process_form_to_config(form_data, schema)
    updated_user["permissions"] = list(
        set(updated_user.get("permissions", []))
        - set(role_map.get(updated_user["role"], {}).get("permissions", []))
    )
    updated_user["deny_permissions"] = list(
        set(updated_user.get("deny_permissions", []))
        - set(role_map.get(updated_user["role"], {}).get("deny_permissions", []))
    )
    updated_user["updated_on"] = util.common.utc_now()
    updated_user["updated_by"] = current_username(default=user.username)
    if updated_user["auth_type"] == "coyote3" and updated_user["password"]:
        updated_user["password"] = util.common.hash_password(updated_user["password"])
    else:
        updated_user["password"] = user_doc.get("password")
    updated_user["schema_name"] = schema.get("schema_id") or schema["_id"]
    updated_user["schema_version"] = schema["version"]
    updated_user["version"] = user_doc.get("version", 1) + 1
    updated_user["user_id"] = user_doc.get("user_id", user_id)
    updated_user["_id"] = user_doc.get("_id")
    updated_user = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=updated_user,
        old_config=user_doc,
        is_new=False,
    )
    _admin_repo().user_handler.update_user(user_id, updated_user)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_id, action="update")
    )


@router.post("/api/v1/admin/users/{user_id}/delete", response_model=AdminMutationPayload)
def delete_user_mutation(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="delete_user", min_role="admin", min_level=99999)),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise api_error(404, "User not found")
    _admin_repo().user_handler.delete_user(user_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_id, action="delete")
    )


@router.post("/api/v1/admin/users/{user_id}/toggle", response_model=AdminMutationPayload)
def toggle_user_mutation(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="edit_user", min_role="admin", min_level=99999)),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise api_error(404, "User not found")
    new_status = not bool(user_doc.get("is_active"))
    _admin_repo().user_handler.toggle_user_active(user_id, new_status)
    result = _mutation_payload("admin", resource="user", resource_id=user_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/users/validate_username", response_model=AdminExistsPayload)
def validate_username_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    username = str(payload.get("username", "")).lower()
    return util.common.convert_to_serializable({"exists": _admin_repo().user_handler.user_exists(user_id=username)})


@router.post("/api/v1/admin/users/validate_email", response_model=AdminExistsPayload)
def validate_email_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    email = str(payload.get("email", "")).lower()
    return util.common.convert_to_serializable({"exists": _admin_repo().user_handler.user_exists(email=email)})


__all__ = [
    "_admin_repo",
    "_admin_repo_instance",
    "_as_dict_rows",
    "_assay_group_map",
    "_mutation_payload",
    "_permission_policy_options",
    "_role_map",
    "_user_role_permission_map",
    "create_user_context_read",
    "create_user_mutation",
    "delete_user_mutation",
    "list_users_read",
    "toggle_user_mutation",
    "update_user_mutation",
    "user_context_read",
    "validate_email_mutation",
    "validate_username_mutation",
]
