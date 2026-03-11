"""Admin API routes."""

from copy import deepcopy

from fastapi import Body, Depends, Query

from api.app import _api_error, app
from api.contracts.admin import (
    AdminAspcContextPayload,
    AdminAspcCreateContextPayload,
    AdminAspcListPayload,
    AdminExistsPayload,
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
    AdminMutationPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
    AdminPermissionContextPayload,
    AdminPermissionCreateContextPayload,
    AdminPermissionsListPayload,
    AdminRoleContextPayload,
    AdminRoleCreateContextPayload,
    AdminRolesListPayload,
    AdminSampleContextPayload,
    AdminSamplesListPayload,
    AdminSchemaContextPayload,
    AdminSchemasListPayload,
    AdminUserContextPayload,
    AdminUserCreateContextPayload,
    AdminUsersListPayload,
)
from api.core.admin.sample_deletion import SampleDeletionService, delete_all_sample_traces
from api.extensions import util
from api.infra.repositories.admin_route_mongo import MongoAdminRouteRepository
from api.infra.repositories.admin_sample_mongo import MongoAdminSampleDeletionRepository
from api.runtime import app as runtime_app, current_username
from api.security.access import ApiUser, require_access


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


_admin_repo_instance: MongoAdminRouteRepository | None = None


def _admin_repo() -> MongoAdminRouteRepository:
    global _admin_repo_instance
    if _admin_repo_instance is None:
        _admin_repo_instance = MongoAdminRouteRepository()
    return _admin_repo_instance


def _active_flag(doc: dict | None, default: bool = True) -> bool:
    if not isinstance(doc, dict):
        return default
    return bool(doc.get("is_active", default))


def _with_active_default(items: list[dict], default: bool = True) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            row = dict(item)
            row.setdefault("is_active", default)
            normalized.append(row)
    return normalized


def _permission_policy_options() -> list[dict]:
    permission_policies = _admin_repo().permissions_handler.get_all_permissions(is_active=True)
    return [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]


def _role_map() -> dict[str, dict]:
    all_roles = _admin_repo().roles_handler.get_all_roles()
    return {
        role["_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }
        for role in all_roles
    }


def _assay_group_map() -> dict[str, list[dict]]:
    assay_groups_panels = _admin_repo().asp_handler.get_all_asps()
    return util.common.create_assay_group_map(assay_groups_panels)


def _sample_deletion_service() -> type[SampleDeletionService]:
    if not SampleDeletionService.has_repository():
        SampleDeletionService.set_repository(MongoAdminSampleDeletionRepository())
    return SampleDeletionService


@app.get("/api/v1/admin/roles", response_model=AdminRolesListPayload)
def list_roles_read(
    user: ApiUser = Depends(
        require_access(permission="view_role", min_role="admin", min_level=99999)
    ),
):
    roles = _with_active_default(_admin_repo().roles_handler.get_all_roles())
    return util.common.convert_to_serializable({"roles": roles})


@app.get("/api/v1/admin/roles/create_context", response_model=AdminRoleCreateContextPayload)
def create_role_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_role", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_role",
        schema_category="RBAC_role",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active role schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

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


@app.get("/api/v1/admin/roles/{role_id}/context", response_model=AdminRoleContextPayload)
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_role", min_role="admin", min_level=99999)
    ),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    schema = _admin_repo().schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for role")

    schema = deepcopy(schema)
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["permissions"]["default"] = role.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")

    return util.common.convert_to_serializable(
        {
            "role": role,
            "schema": schema,
        }
    )


@app.post("/api/v1/admin/permissions/create", response_model=AdminMutationPayload)
def create_permission_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active permission schemas found")

    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise _api_error(404, "Selected schema not found")

    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    form_data = payload.get("form_data", {})
    policy = util.admin.process_form_to_config(form_data, schema)
    policy.setdefault("is_active", True)
    policy["_id"] = policy["permission_name"]
    policy["schema_name"] = schema["_id"]
    policy["schema_version"] = schema["version"]
    policy = util.admin.inject_version_history(
        user_email=current_username(default=user.username),
        new_config=deepcopy(policy),
        is_new=True,
    )
    _admin_repo().permissions_handler.create_new_policy(policy)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin", resource="permission", resource_id=policy["_id"], action="create"
        )
    )


@app.get("/api/v1/admin/permissions", response_model=AdminPermissionsListPayload)
def list_permissions_read(
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission_policies = _with_active_default(
        _admin_repo().permissions_handler.get_all_permissions(is_active=False)
    )
    grouped_permissions: dict[str, list[dict]] = {}
    for policy in permission_policies:
        grouped_permissions.setdefault(policy.get("category", "Uncategorized"), []).append(policy)
    return util.common.convert_to_serializable(
        {
            "permission_policies": permission_policies,
            "grouped_permissions": grouped_permissions,
        }
    )


@app.get(
    "/api/v1/admin/permissions/create_context", response_model=AdminPermissionCreateContextPayload
)
def create_permission_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active permission schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
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


@app.get(
    "/api/v1/admin/permissions/{perm_id}/context", response_model=AdminPermissionContextPayload
)
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission = _admin_repo().permissions_handler.get(perm_id)
    if not permission:
        raise _api_error(404, "Permission policy not found")
    schema = _admin_repo().schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for permission policy")
    return util.common.convert_to_serializable(
        {
            "permission": permission,
            "schema": schema,
        }
    )


@app.post("/api/v1/admin/permissions/{perm_id}/update", response_model=AdminMutationPayload)
def update_permission_mutation(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission = _admin_repo().permissions_handler.get(perm_id)
    if not permission:
        raise _api_error(404, "Permission policy not found")
    schema = _admin_repo().schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for permission policy")

    form_data = payload.get("form_data", {})
    updated_permission = util.admin.process_form_to_config(form_data, schema)
    updated_permission["updated_on"] = util.common.utc_now()
    updated_permission["updated_by"] = current_username(default=user.username)
    updated_permission["version"] = permission.get("version", 1) + 1
    updated_permission["schema_name"] = schema["_id"]
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


@app.post("/api/v1/admin/permissions/{perm_id}/toggle", response_model=AdminMutationPayload)
def toggle_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
):
    perm = _admin_repo().permissions_handler.get(perm_id)
    if not perm:
        raise _api_error(404, "Permission policy not found")
    new_status = not _active_flag(perm)
    _admin_repo().permissions_handler.toggle_policy_active(perm_id, new_status)
    result = _mutation_payload("admin", resource="permission", resource_id=perm_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/permissions/{perm_id}/delete", response_model=AdminMutationPayload)
def delete_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_permission_policy", min_role="admin", min_level=99999)
    ),
):
    perm = _admin_repo().permissions_handler.get(perm_id)
    if not perm:
        raise _api_error(404, "Permission policy not found")
    _admin_repo().permissions_handler.delete_policy(perm_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=perm_id, action="delete")
    )


@app.post("/api/v1/admin/roles/create", response_model=AdminMutationPayload)
def create_role_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_role", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_role",
        schema_category="RBAC_role",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active role schemas found")
    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise _api_error(404, "Selected schema not found")

    form_data = payload.get("form_data", {})
    role = util.admin.process_form_to_config(form_data, schema)
    role.setdefault("is_active", True)
    role["_id"] = role.get("name")
    role["schema_name"] = schema["_id"]
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


@app.post("/api/v1/admin/roles/{role_id}/update", response_model=AdminMutationPayload)
def update_role_mutation(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_role", min_role="admin", min_level=99999)
    ),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    schema = _admin_repo().schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for role")

    form_data = payload.get("form_data", {})
    updated_role = util.admin.process_form_to_config(form_data, schema)
    updated_role["updated_by"] = current_username(default=user.username)
    updated_role["updated_on"] = util.common.utc_now()
    updated_role["schema_name"] = schema["_id"]
    updated_role["schema_version"] = schema["version"]
    updated_role["version"] = role.get("version", 1) + 1
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


@app.post("/api/v1/admin/roles/{role_id}/toggle", response_model=AdminMutationPayload)
def toggle_role_mutation(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_role", min_role="admin", min_level=99999)
    ),
):
    role = _admin_repo().roles_handler.get(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    new_status = not _active_flag(role)
    _admin_repo().roles_handler.toggle_role_active(role_id, new_status)
    result = _mutation_payload("admin", resource="role", resource_id=role_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/roles/{role_id}/delete", response_model=AdminMutationPayload)
def delete_role_mutation(
    role_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_role", min_role="admin", min_level=99999)
    ),
):
    role = _admin_repo().roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    _admin_repo().roles_handler.delete_role(role_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role_id, action="delete")
    )


@app.get("/api/v1/admin/users", response_model=AdminUsersListPayload)
def list_users_read(
    user: ApiUser = Depends(
        require_access(permission="view_user", min_role="admin", min_level=99999)
    ),
):
    users = _with_active_default(_admin_repo().user_handler.get_all_users())
    roles = _admin_repo().roles_handler.get_role_colors()
    return util.common.convert_to_serializable(
        {
            "users": users,
            "roles": roles,
        }
    )


@app.get("/api/v1/admin/users/create_context", response_model=AdminUserCreateContextPayload)
def create_user_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active user schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "User schema not found")

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


@app.get("/api/v1/admin/users/{user_id}/context", response_model=AdminUserContextPayload)
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_user", min_role="admin", min_level=99999)
    ),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")

    schema = _admin_repo().schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for user")

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


@app.post("/api/v1/admin/users/create", response_model=AdminMutationPayload)
def create_user_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active user schemas found")
    selected_id = payload.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        raise _api_error(404, "User schema not found")

    all_roles = _admin_repo().roles_handler.get_all_roles()
    role_map = {
        role["_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
        }
        for role in all_roles
    }

    form_data = payload.get("form_data", {})
    role_permissions = role_map.get(form_data.get("role"), {})
    form_data["permissions"] = list(
        set(form_data.get("permissions", [])) - set(role_permissions.get("permissions", []))
    )
    form_data["deny_permissions"] = list(
        set(form_data.get("deny_permissions", []))
        - set(role_permissions.get("deny_permissions", []))
    )
    user_data = util.admin.process_form_to_config(form_data, schema)
    user_data.setdefault("is_active", True)
    user_data["_id"] = user_data["username"]
    user_data["schema_name"] = schema["_id"]
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
        _mutation_payload(
            "admin", resource="user", resource_id=user_data["username"], action="create"
        )
    )


@app.post("/api/v1/admin/users/{user_id}/update", response_model=AdminMutationPayload)
def update_user_mutation(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_user", min_role="admin", min_level=99999)
    ),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    schema = _admin_repo().schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for user")

    all_roles = _admin_repo().roles_handler.get_all_roles()
    role_map = {
        role["_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
        }
        for role in all_roles
    }

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
    updated_user["schema_name"] = schema["_id"]
    updated_user["schema_version"] = schema["version"]
    updated_user["version"] = user_doc.get("version", 1) + 1
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


@app.post("/api/v1/admin/users/{user_id}/delete", response_model=AdminMutationPayload)
def delete_user_mutation(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_user", min_role="admin", min_level=99999)
    ),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    _admin_repo().user_handler.delete_user(user_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_id, action="delete")
    )


@app.post("/api/v1/admin/users/{user_id}/toggle", response_model=AdminMutationPayload)
def toggle_user_mutation(
    user_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_user", min_role="admin", min_level=99999)
    ),
):
    user_doc = _admin_repo().user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    new_status = not _active_flag(user_doc)
    _admin_repo().user_handler.toggle_user_active(user_id, new_status)
    result = _mutation_payload("admin", resource="user", resource_id=user_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/users/validate_username", response_model=AdminExistsPayload)
def validate_username_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
):
    username = str(payload.get("username", "")).lower()
    return util.common.convert_to_serializable(
        {"exists": _admin_repo().user_handler.user_exists(user_id=username)}
    )


@app.post("/api/v1/admin/users/validate_email", response_model=AdminExistsPayload)
def validate_email_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_user", min_role="admin", min_level=99999)
    ),
):
    email = str(payload.get("email", "")).lower()
    return util.common.convert_to_serializable(
        {"exists": _admin_repo().user_handler.user_exists(email=email)}
    )


@app.post("/api/v1/admin/asp/create", response_model=AdminMutationPayload)
def create_asp_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing panel config payload")
    config.setdefault("is_active", True)
    _admin_repo().asp_handler.create_asp(config)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin", resource="asp", resource_id=str(config.get("_id", "unknown")), action="create"
        )
    )


@app.get("/api/v1/admin/asp", response_model=AdminPanelsListPayload)
def list_asp_read(
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
):
    panels = _with_active_default(_admin_repo().asp_handler.get_all_asps())
    return util.common.convert_to_serializable({"panels": panels})


@app.get("/api/v1/admin/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_asp", min_role="manager", min_level=99)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="asp_schema",
        schema_category="ASP",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active panel schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
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


@app.get("/api/v1/admin/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
):
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")

    schema = _admin_repo().schema_handler.get_schema(panel.get("schema_name", "ASP-Schema"))
    if not schema:
        raise _api_error(404, "Schema not found for panel")

    return util.common.convert_to_serializable({"panel": panel, "schema": schema})


@app.post("/api/v1/admin/asp/{assay_panel_id}/update", response_model=AdminMutationPayload)
def update_asp_mutation(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
):
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing panel config payload")
    _admin_repo().asp_handler.update_asp(assay_panel_id, updated)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="update")
    )


@app.post("/api/v1/admin/asp/{assay_panel_id}/toggle", response_model=AdminMutationPayload)
def toggle_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_asp", min_role="manager", min_level=99)
    ),
):
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    new_status = not _active_flag(panel)
    _admin_repo().asp_handler.toggle_asp_active(assay_panel_id, new_status)
    result = _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/asp/{assay_panel_id}/delete", response_model=AdminMutationPayload)
def delete_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_asp", min_role="admin", min_level=99999)
    ),
):
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    _admin_repo().asp_handler.delete_asp(assay_panel_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="delete")
    )


@app.post("/api/v1/admin/genelists/create", response_model=AdminMutationPayload)
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_isgl", min_role="manager", min_level=99)
    ),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing genelist config payload")
    config.setdefault("is_active", True)
    _admin_repo().isgl_handler.create_isgl(config)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin",
            resource="genelist",
            resource_id=str(config.get("_id", "unknown")),
            action="create",
        )
    )


@app.get("/api/v1/admin/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelists = _with_active_default(_admin_repo().isgl_handler.get_all_isgl())
    return util.common.convert_to_serializable({"genelists": genelists})


@app.get("/api/v1/admin/genelists/create_context", response_model=AdminGenelistCreateContextPayload)
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_isgl", min_role="manager", min_level=99)
    ),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="isgl_config",
        schema_category="ISGL",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active genelist schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Genelist schema not found")

    schema = deepcopy(selected_schema)
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
            "assay_group_map": _assay_group_map(),
        }
    )


@app.get(
    "/api/v1/admin/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload
)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    schema = _admin_repo().schema_handler.get_schema(genelist.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for genelist")

    schema = deepcopy(schema)
    schema["fields"]["assay_groups"]["options"] = _admin_repo().asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
    schema["fields"]["assays"]["default"] = genelist.get("assays", [])

    return util.common.convert_to_serializable(
        {
            "genelist": genelist,
            "schema": schema,
            "assay_group_map": _assay_group_map(),
        }
    )


@app.get(
    "/api/v1/admin/genelists/{genelist_id}/view_context",
    response_model=AdminGenelistViewContextPayload,
)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])
    filtered_genes = all_genes
    panel_germline_genes: list[str] = []

    if assay and assay in assays:
        panel = _admin_repo().asp_handler.get_asp(assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        panel_germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = sorted(set(all_genes).intersection(panel_genes))

    return util.common.convert_to_serializable(
        {
            "genelist": genelist,
            "selected_assay": assay,
            "filtered_genes": filtered_genes,
            "panel_germline_genes": panel_germline_genes,
        }
    )


@app.post("/api/v1/admin/genelists/{genelist_id}/update", response_model=AdminMutationPayload)
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_isgl", min_role="manager", min_level=99)
    ),
):
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing genelist config payload")
    _admin_repo().isgl_handler.update_isgl(genelist_id, updated)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="update")
    )


@app.post("/api/v1/admin/genelists/{genelist_id}/toggle", response_model=AdminMutationPayload)
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_isgl", min_role="manager", min_level=99)
    ),
):
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    new_status = not _active_flag(genelist)
    _admin_repo().isgl_handler.toggle_isgl_active(genelist_id, new_status)
    result = _mutation_payload(
        "admin", resource="genelist", resource_id=genelist_id, action="toggle"
    )
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/genelists/{genelist_id}/delete", response_model=AdminMutationPayload)
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_isgl", min_role="admin", min_level=99999)
    ),
):
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    _admin_repo().isgl_handler.delete_isgl(genelist_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="delete")
    )


@app.get("/api/v1/admin/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
):
    assay_configs = _with_active_default(list(_admin_repo().aspc_handler.get_all_aspc()))
    return util.common.convert_to_serializable({"assay_configs": assay_configs})


@app.get("/api/v1/admin/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_aspc", min_role="manager", min_level=99)
    ),
):
    schema_category = str(category or "DNA").upper()
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="asp_config",
        schema_category=schema_category,
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, f"No active {schema_category} schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
    assay_panels = _admin_repo().asp_handler.get_all_asps(is_active=True)
    prefill_map: dict[str, dict] = {}
    valid_assay_ids: list[str] = []

    for panel in assay_panels:
        if panel.get("asp_category") == schema_category:
            envs = _admin_repo().aspc_handler.get_available_assay_envs(
                panel["_id"], schema["fields"]["environment"]["options"]
            )
            if envs:
                valid_assay_ids.append(panel["_id"])
                prefill_map[panel["_id"]] = {
                    "display_name": panel.get("display_name"),
                    "asp_group": panel.get("asp_group"),
                    "asp_category": panel.get("asp_category"),
                    "platform": panel.get("platform"),
                    "environment": envs,
                }

    schema["fields"]["assay_name"]["options"] = valid_assay_ids
    if schema_category == "DNA" and "vep_consequences" in schema.get("fields", {}):
        schema["fields"]["vep_consequences"]["options"] = list(
            runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
        )
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "category": schema_category,
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
            "prefill_map": prefill_map,
        }
    )


@app.get("/api/v1/admin/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
):
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")

    schema = _admin_repo().schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema for this assay config is missing")
    schema = deepcopy(schema)
    if "vep_consequences" in schema.get("fields", {}):
        schema["fields"]["vep_consequences"]["options"] = list(
            runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
        )

    return util.common.convert_to_serializable({"assay_config": assay_config, "schema": schema})


@app.post("/api/v1/admin/aspc/create", response_model=AdminMutationPayload)
def create_aspc_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_aspc", min_role="manager", min_level=99)
    ),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing assay config payload")
    config.setdefault("is_active", True)
    existing_config = _admin_repo().aspc_handler.get_aspc_with_id(config.get("_id"))
    if existing_config:
        raise _api_error(409, "Assay config already exists")
    _admin_repo().aspc_handler.create_aspc(config)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin", resource="aspc", resource_id=str(config.get("_id", "unknown")), action="create"
        )
    )


@app.post("/api/v1/admin/aspc/{assay_id}/update", response_model=AdminMutationPayload)
def update_aspc_mutation(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_aspc", min_role="manager", min_level=99)
    ),
):
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    updated_config = payload.get("config", {})
    if not updated_config:
        raise _api_error(400, "Missing assay config payload")
    _admin_repo().aspc_handler.update_aspc(assay_id, updated_config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="update")
    )


@app.post("/api/v1/admin/aspc/{assay_id}/toggle", response_model=AdminMutationPayload)
def toggle_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_aspc", min_role="manager", min_level=99)
    ),
):
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    new_status = not _active_flag(assay_config)
    _admin_repo().aspc_handler.toggle_aspc_active(assay_id, new_status)
    result = _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/aspc/{assay_id}/delete", response_model=AdminMutationPayload)
def delete_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_aspc", min_role="admin", min_level=99999)
    ),
):
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    _admin_repo().aspc_handler.delete_aspc(assay_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="delete")
    )


@app.get("/api/v1/admin/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    user: ApiUser = Depends(
        require_access(permission="view_sample_global", min_role="developer", min_level=9999)
    ),
):
    samples = list(_admin_repo().sample_handler.get_all_samples(user.assays, None, search))
    return util.common.convert_to_serializable({"samples": samples})


@app.get("/api/v1/admin/samples/{sample_id}/context", response_model=AdminSampleContextPayload)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_sample", min_role="developer", min_level=9999)
    ),
):
    sample_doc = _admin_repo().sample_handler.get_sample(sample_id)
    if not sample_doc:
        raise _api_error(404, "Sample not found")
    return util.common.convert_to_serializable({"sample": sample_doc})


@app.post("/api/v1/admin/samples/{sample_id}/update", response_model=AdminMutationPayload)
def update_sample_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_sample", min_role="developer", min_level=9999)
    ),
):
    sample_doc = _admin_repo().sample_handler.get_sample(sample_id)
    if not sample_doc:
        raise _api_error(404, "Sample not found")
    sample_obj = sample_doc.get("_id")
    updated_sample = payload.get("sample", {})
    if not updated_sample:
        raise _api_error(400, "Missing sample payload")
    updated_sample["updated_on"] = util.common.utc_now()
    updated_sample["updated_by"] = current_username(default=user.username)
    updated_sample = util.admin.restore_objectids(deepcopy(updated_sample))
    updated_sample["_id"] = sample_obj
    _admin_repo().sample_handler.update_sample(sample_obj, updated_sample)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="sample", resource_id=str(sample_obj), action="update")
    )


@app.post("/api/v1/admin/samples/{sample_id}/delete", response_model=AdminMutationPayload)
def delete_sample_mutation(
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_sample_global", min_role="developer", min_level=9999)
    ),
):
    _sample_deletion_service()
    sample_name = _admin_repo().sample_handler.get_sample_name(sample_id)
    if not sample_name:
        raise _api_error(404, "Sample not found")
    deletion_summary = delete_all_sample_traces(sample_id)
    result = _mutation_payload("admin", resource="sample", resource_id=sample_id, action="delete")
    result["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
    result["meta"]["results"] = deletion_summary.get("results", [])
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/schemas/create", response_model=AdminMutationPayload)
def create_schema_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_schema", min_role="developer", min_level=9999)
    ),
):
    schema_doc = payload.get("schema", {})
    schema_doc["_id"] = schema_doc.get("schema_name")
    schema_doc.setdefault("is_active", True)
    schema_doc["created_on"] = util.common.utc_now()
    schema_doc["created_by"] = current_username(default=user.username)
    schema_doc["updated_on"] = util.common.utc_now()
    schema_doc["updated_by"] = current_username(default=user.username)
    _admin_repo().schema_handler.create_schema(schema_doc)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin", resource="schema", resource_id=schema_doc["_id"], action="create"
        )
    )


@app.get("/api/v1/admin/schemas", response_model=AdminSchemasListPayload)
def list_schemas_read(
    user: ApiUser = Depends(
        require_access(permission="view_schema", min_role="developer", min_level=9999)
    ),
):
    schemas = _with_active_default(list(_admin_repo().schema_handler.get_all_schemas()))
    return util.common.convert_to_serializable({"schemas": schemas})


@app.get("/api/v1/admin/schemas/{schema_id}/context", response_model=AdminSchemaContextPayload)
def schema_context_read(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_schema", min_role="developer", min_level=9999)
    ),
):
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    return util.common.convert_to_serializable({"schema": schema_doc})


@app.post("/api/v1/admin/schemas/{schema_id}/update", response_model=AdminMutationPayload)
def update_schema_mutation(
    schema_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_schema", min_role="developer", min_level=9999)
    ),
):
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    updated_schema = payload.get("schema", {})
    updated_schema["_id"] = schema_doc["_id"]
    updated_schema["updated_on"] = util.common.utc_now()
    updated_schema["updated_by"] = current_username(default=user.username)
    updated_schema["version"] = schema_doc.get("version", 1) + 1
    _admin_repo().schema_handler.update_schema(schema_id, updated_schema)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="schema", resource_id=schema_id, action="update")
    )


@app.post("/api/v1/admin/schemas/{schema_id}/toggle", response_model=AdminMutationPayload)
def toggle_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_schema", min_role="developer", min_level=9999)
    ),
):
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    new_status = not _active_flag(schema_doc)
    _admin_repo().schema_handler.toggle_schema_active(schema_id, new_status)
    result = _mutation_payload("admin", resource="schema", resource_id=schema_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/schemas/{schema_id}/delete", response_model=AdminMutationPayload)
def delete_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_schema", min_role="admin", min_level=99999)
    ),
):
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    _admin_repo().schema_handler.delete_schema(schema_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="schema", resource_id=schema_id, action="delete")
    )
