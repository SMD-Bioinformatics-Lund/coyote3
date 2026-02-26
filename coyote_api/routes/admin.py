"""Admin API routes."""

from copy import deepcopy

from fastapi import Body, Depends, Query

from coyote.extensions import store, util
from coyote_api.app import ApiUser, _api_error, _get_sample_for_api, app, require_access


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
    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    return [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]


def _role_map() -> dict[str, dict]:
    all_roles = store.roles_handler.get_all_roles()
    return {
        role["_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }
        for role in all_roles
    }


def _assay_group_map() -> dict[str, list[dict]]:
    assay_groups_panels = store.asp_handler.get_all_asps()
    return util.common.create_assay_group_map(assay_groups_panels)


@app.get("/api/v1/admin/roles")
def list_roles_read(
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
):
    roles = store.roles_handler.get_all_roles()
    return util.common.convert_to_serializable({"roles": roles})


@app.get("/api/v1/admin/roles/create_context")
def create_role_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
        }
    )


@app.get("/api/v1/admin/roles/{role_id}/context")
def role_context_read(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="view_role", min_role="admin", min_level=99999)),
):
    role = store.roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    schema = store.schema_handler.get_schema(role.get("schema_name"))
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


@app.post("/api/v1/admin/permissions/create")
def create_permission_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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

    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    form_data = payload.get("form_data", {})
    policy = util.admin.process_form_to_config(form_data, schema)
    policy["_id"] = policy["permission_name"]
    policy["schema_name"] = schema["_id"]
    policy["schema_version"] = schema["version"]
    policy = util.admin.inject_version_history(
        user_email=user.username,
        new_config=deepcopy(policy),
        is_new=True,
    )
    store.permissions_handler.create_new_policy(policy)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=policy["_id"], action="create")
    )


@app.get("/api/v1/admin/permissions")
def list_permissions_read(
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission_policies = store.permissions_handler.get_all_permissions(is_active=False)
    grouped_permissions: dict[str, list[dict]] = {}
    for policy in permission_policies:
        grouped_permissions.setdefault(policy.get("category", "Uncategorized"), []).append(policy)
    return util.common.convert_to_serializable(
        {
            "permission_policies": permission_policies,
            "grouped_permissions": grouped_permissions,
        }
    )


@app.get("/api/v1/admin/permissions/create_context")
def create_permission_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(
        require_access(permission="create_permission_policy", min_role="admin", min_level=99999)
    ),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
        }
    )


@app.get("/api/v1/admin/permissions/{perm_id}/context")
def permission_context_read(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="view_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        raise _api_error(404, "Permission policy not found")
    schema = store.schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for permission policy")
    return util.common.convert_to_serializable(
        {
            "permission": permission,
            "schema": schema,
        }
    )


@app.post("/api/v1/admin/permissions/{perm_id}/update")
def update_permission_mutation(
    perm_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
):
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        raise _api_error(404, "Permission policy not found")
    schema = store.schema_handler.get_schema(permission.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for permission policy")

    form_data = payload.get("form_data", {})
    updated_permission = util.admin.process_form_to_config(form_data, schema)
    updated_permission["updated_on"] = util.common.utc_now()
    updated_permission["updated_by"] = user.username
    updated_permission["version"] = permission.get("version", 1) + 1
    updated_permission["schema_name"] = schema["_id"]
    updated_permission["schema_version"] = schema["version"]
    updated_permission = util.admin.inject_version_history(
        user_email=user.username,
        new_config=updated_permission,
        old_config=permission,
        is_new=False,
    )
    store.permissions_handler.update_policy(perm_id, updated_permission)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=perm_id, action="update")
    )


@app.post("/api/v1/admin/permissions/{perm_id}/toggle")
def toggle_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_permission_policy", min_role="admin", min_level=99999)
    ),
):
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        raise _api_error(404, "Permission policy not found")
    new_status = not perm.get("is_active", False)
    store.permissions_handler.toggle_policy_active(perm_id, new_status)
    result = _mutation_payload("admin", resource="permission", resource_id=perm_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/permissions/{perm_id}/delete")
def delete_permission_mutation(
    perm_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_permission_policy", min_role="admin", min_level=99999)
    ),
):
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        raise _api_error(404, "Permission policy not found")
    store.permissions_handler.delete_policy(perm_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="permission", resource_id=perm_id, action="delete")
    )


@app.post("/api/v1/admin/roles/create")
def create_role_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_role", min_role="admin", min_level=99999)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    role["_id"] = role.get("name")
    role["schema_name"] = schema["_id"]
    role["schema_version"] = schema["version"]
    role = util.admin.inject_version_history(
        user_email=user.username,
        new_config=deepcopy(role),
        is_new=True,
    )
    store.roles_handler.create_role(role)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role["_id"], action="create")
    )


@app.post("/api/v1/admin/roles/{role_id}/update")
def update_role_mutation(
    role_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
):
    role = store.roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    schema = store.schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for role")

    form_data = payload.get("form_data", {})
    updated_role = util.admin.process_form_to_config(form_data, schema)
    updated_role["updated_by"] = user.username
    updated_role["updated_on"] = util.common.utc_now()
    updated_role["schema_name"] = schema["_id"]
    updated_role["schema_version"] = schema["version"]
    updated_role["version"] = role.get("version", 1) + 1
    updated_role["_id"] = role.get("_id")
    updated_role = util.admin.inject_version_history(
        user_email=user.username,
        new_config=updated_role,
        old_config=role,
        is_new=False,
    )
    store.roles_handler.update_role(role_id, updated_role)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role_id, action="update")
    )


@app.post("/api/v1/admin/roles/{role_id}/toggle")
def toggle_role_mutation(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="edit_role", min_role="admin", min_level=99999)),
):
    role = store.roles_handler.get(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    new_status = not role.get("is_active", False)
    store.roles_handler.toggle_role_active(role_id, new_status)
    result = _mutation_payload("admin", resource="role", resource_id=role_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/roles/{role_id}/delete")
def delete_role_mutation(
    role_id: str,
    user: ApiUser = Depends(require_access(permission="delete_role", min_role="admin", min_level=99999)),
):
    role = store.roles_handler.get_role(role_id)
    if not role:
        raise _api_error(404, "Role not found")
    store.roles_handler.delete_role(role_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="role", resource_id=role_id, action="delete")
    )


@app.get("/api/v1/admin/users")
def list_users_read(
    user: ApiUser = Depends(require_access(permission="view_user", min_role="admin", min_level=99999)),
):
    users = store.user_handler.get_all_users()
    roles = store.roles_handler.get_role_colors()
    return util.common.convert_to_serializable(
        {
            "users": users,
            "roles": roles,
        }
    )


@app.get("/api/v1/admin/users/create_context")
def create_user_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    schema["fields"]["role"]["options"] = store.roles_handler.get_all_role_names()
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["assay_groups"]["options"] = store.asp_handler.get_all_asp_groups()
    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
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


@app.get("/api/v1/admin/users/{user_id}/context")
def user_context_read(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="view_user", min_role="admin", min_level=99999)),
):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")

    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for user")

    schema = deepcopy(schema)
    schema["fields"]["role"]["options"] = store.roles_handler.get_all_role_names()
    options = _permission_policy_options()
    schema["fields"]["permissions"]["options"] = options
    schema["fields"]["deny_permissions"]["options"] = options
    schema["fields"]["permissions"]["default"] = user_doc.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = user_doc.get("deny_permissions")
    schema["fields"]["assay_groups"]["options"] = store.asp_handler.get_all_asp_groups()
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


@app.post("/api/v1/admin/users/create")
def create_user_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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

    all_roles = store.roles_handler.get_all_roles()
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
        set(form_data.get("deny_permissions", [])) - set(role_permissions.get("deny_permissions", []))
    )
    user_data = util.admin.process_form_to_config(form_data, schema)
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
        user_email=user.username,
        new_config=deepcopy(user_data),
        is_new=True,
    )
    store.user_handler.create_user(user_data)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_data["username"], action="create")
    )


@app.post("/api/v1/admin/users/{user_id}/update")
def update_user_mutation(
    user_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_user", min_role="admin", min_level=99999)),
):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for user")

    all_roles = store.roles_handler.get_all_roles()
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
    updated_user["updated_by"] = user.username
    if updated_user["auth_type"] == "coyote3" and updated_user["password"]:
        updated_user["password"] = util.common.hash_password(updated_user["password"])
    else:
        updated_user["password"] = user_doc.get("password")
    updated_user["schema_name"] = schema["_id"]
    updated_user["schema_version"] = schema["version"]
    updated_user["version"] = user_doc.get("version", 1) + 1
    updated_user = util.admin.inject_version_history(
        user_email=user.username,
        new_config=updated_user,
        old_config=user_doc,
        is_new=False,
    )
    store.user_handler.update_user(user_id, updated_user)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_id, action="update")
    )


@app.post("/api/v1/admin/users/{user_id}/delete")
def delete_user_mutation(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="delete_user", min_role="admin", min_level=99999)),
):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    store.user_handler.delete_user(user_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="user", resource_id=user_id, action="delete")
    )


@app.post("/api/v1/admin/users/{user_id}/toggle")
def toggle_user_mutation(
    user_id: str,
    user: ApiUser = Depends(require_access(permission="edit_user", min_role="admin", min_level=99999)),
):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(404, "User not found")
    new_status = not user_doc.get("is_active", False)
    store.user_handler.toggle_user_active(user_id, new_status)
    result = _mutation_payload("admin", resource="user", resource_id=user_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/users/validate_username")
def validate_username_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    username = str(payload.get("username", "")).lower()
    return util.common.convert_to_serializable({"exists": store.user_handler.user_exists(user_id=username)})


@app.post("/api/v1/admin/users/validate_email")
def validate_email_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_user", min_role="admin", min_level=99999)),
):
    email = str(payload.get("email", "")).lower()
    return util.common.convert_to_serializable({"exists": store.user_handler.user_exists(email=email)})


@app.post("/api/v1/admin/asp/create")
def create_asp_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing panel config payload")
    store.asp_handler.create_asp(config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=str(config.get("_id", "unknown")), action="create")
    )


@app.get("/api/v1/admin/asp")
def list_asp_read(
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
):
    panels = store.asp_handler.get_all_asps()
    return util.common.convert_to_serializable({"panels": panels})


@app.get("/api/v1/admin/asp/create_context")
def create_asp_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
        }
    )


@app.get("/api/v1/admin/asp/{assay_panel_id}/context")
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
):
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")

    schema = store.schema_handler.get_schema(panel.get("schema_name", "ASP-Schema"))
    if not schema:
        raise _api_error(404, "Schema not found for panel")

    return util.common.convert_to_serializable({"panel": panel, "schema": schema})


@app.post("/api/v1/admin/asp/{assay_panel_id}/update")
def update_asp_mutation(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
):
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing panel config payload")
    store.asp_handler.update_asp(assay_panel_id, updated)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="update")
    )


@app.post("/api/v1/admin/asp/{assay_panel_id}/toggle")
def toggle_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
):
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    new_status = not panel.get("is_active", False)
    store.asp_handler.toggle_asp_active(assay_panel_id, new_status)
    result = _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/asp/{assay_panel_id}/delete")
def delete_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="delete_asp", min_role="admin", min_level=99999)),
):
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    store.asp_handler.delete_asp(assay_panel_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="delete")
    )


@app.post("/api/v1/admin/genelists/create")
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing genelist config payload")
    store.isgl_handler.create_isgl(config)
    return util.common.convert_to_serializable(
        _mutation_payload(
            "admin",
            resource="genelist",
            resource_id=str(config.get("_id", "unknown")),
            action="create",
        )
    )


@app.get("/api/v1/admin/genelists")
def list_genelists_read(
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelists = store.isgl_handler.get_all_isgl()
    return util.common.convert_to_serializable({"genelists": genelists})


@app.get("/api/v1/admin/genelists/create_context")
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
):
    active_schemas = store.schema_handler.get_schemas_by_category_type(
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
    schema["fields"]["assay_groups"]["options"] = store.asp_handler.get_all_asp_groups()
    schema["fields"]["created_by"]["default"] = user.username
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = user.username
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {
            "schemas": active_schemas,
            "selected_schema": selected_schema,
            "schema": schema,
            "assay_group_map": _assay_group_map(),
        }
    )


@app.get("/api/v1/admin/genelists/{genelist_id}/context")
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    schema = store.schema_handler.get_schema(genelist.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for genelist")

    schema = deepcopy(schema)
    schema["fields"]["assay_groups"]["options"] = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
    schema["fields"]["assays"]["default"] = genelist.get("assays", [])

    return util.common.convert_to_serializable(
        {
            "genelist": genelist,
            "schema": schema,
            "assay_group_map": _assay_group_map(),
        }
    )


@app.get("/api/v1/admin/genelists/{genelist_id}/view_context")
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])
    filtered_genes = all_genes
    panel_germline_genes: list[str] = []

    if assay and assay in assays:
        panel = store.asp_handler.get_asp(assay)
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


@app.post("/api/v1/admin/genelists/{genelist_id}/update")
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
):
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing genelist config payload")
    store.isgl_handler.update_isgl(genelist_id, updated)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="update")
    )


@app.post("/api/v1/admin/genelists/{genelist_id}/toggle")
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
):
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    new_status = not genelist.get("is_active", True)
    store.isgl_handler.toggle_isgl_active(genelist_id, new_status)
    result = _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/genelists/{genelist_id}/delete")
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="delete_isgl", min_role="admin", min_level=99999)),
):
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    store.isgl_handler.delete_isgl(genelist_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="delete")
    )


@app.post("/api/v1/admin/aspc/create")
def create_aspc_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_aspc", min_role="manager", min_level=99)),
):
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing assay config payload")
    existing_config = store.aspc_handler.get_aspc_with_id(config.get("_id"))
    if existing_config:
        raise _api_error(409, "Assay config already exists")
    store.aspc_handler.create_aspc(config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=str(config.get("_id", "unknown")), action="create")
    )


@app.post("/api/v1/admin/aspc/{assay_id}/update")
def update_aspc_mutation(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
):
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    updated_config = payload.get("config", {})
    if not updated_config:
        raise _api_error(400, "Missing assay config payload")
    store.aspc_handler.update_aspc(assay_id, updated_config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="update")
    )


@app.post("/api/v1/admin/aspc/{assay_id}/toggle")
def toggle_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
):
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    new_status = not assay_config.get("is_active", False)
    store.aspc_handler.toggle_aspc_active(assay_id, new_status)
    result = _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/aspc/{assay_id}/delete")
def delete_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="delete_aspc", min_role="admin", min_level=99999)),
):
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    store.aspc_handler.delete_aspc(assay_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="delete")
    )


@app.post("/api/v1/admin/samples/{sample_id}/update")
def update_sample_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
):
    sample_doc = store.sample_handler.get_sample(sample_id)
    if not sample_doc:
        raise _api_error(404, "Sample not found")
    sample_obj = sample_doc.get("_id")
    updated_sample = payload.get("sample", {})
    if not updated_sample:
        raise _api_error(400, "Missing sample payload")
    updated_sample["updated_on"] = util.common.utc_now()
    updated_sample["updated_by"] = user.username
    updated_sample = util.admin.restore_objectids(deepcopy(updated_sample))
    updated_sample["_id"] = sample_obj
    store.sample_handler.update_sample(sample_obj, updated_sample)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="sample", resource_id=str(sample_obj), action="update")
    )


@app.post("/api/v1/admin/samples/{sample_id}/delete")
def delete_sample_mutation(
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_sample_global", min_role="developer", min_level=9999)
    ),
):
    sample_name = store.sample_handler.get_sample_name(sample_id)
    if not sample_name:
        raise _api_error(404, "Sample not found")
    util.admin.delete_all_sample_traces(sample_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="sample", resource_id=sample_id, action="delete")
    )


@app.post("/api/v1/admin/schemas/create")
def create_schema_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_schema", min_role="developer", min_level=9999)),
):
    schema_doc = payload.get("schema", {})
    schema_doc["_id"] = schema_doc.get("schema_name")
    schema_doc["created_on"] = util.common.utc_now()
    schema_doc["created_by"] = user.username
    schema_doc["updated_on"] = util.common.utc_now()
    schema_doc["updated_by"] = user.username
    store.schema_handler.create_schema(schema_doc)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="schema", resource_id=schema_doc["_id"], action="create")
    )


@app.get("/api/v1/admin/schemas")
def list_schemas_read(
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
):
    schemas = store.schema_handler.get_all_schemas()
    return util.common.convert_to_serializable({"schemas": schemas})


@app.get("/api/v1/admin/schemas/{schema_id}/context")
def schema_context_read(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
):
    schema_doc = store.schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    return util.common.convert_to_serializable({"schema": schema_doc})


@app.post("/api/v1/admin/schemas/{schema_id}/update")
def update_schema_mutation(
    schema_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
):
    schema_doc = store.schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    updated_schema = payload.get("schema", {})
    updated_schema["_id"] = schema_doc["_id"]
    updated_schema["updated_on"] = util.common.utc_now()
    updated_schema["updated_by"] = user.username
    updated_schema["version"] = schema_doc.get("version", 1) + 1
    store.schema_handler.update_schema(schema_id, updated_schema)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="schema", resource_id=schema_id, action="update")
    )


@app.post("/api/v1/admin/schemas/{schema_id}/toggle")
def toggle_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
):
    schema_doc = store.schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    new_status = not schema_doc.get("is_active", False)
    store.schema_handler.toggle_schema_active(schema_id, new_status)
    result = _mutation_payload("admin", resource="schema", resource_id=schema_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/admin/schemas/{schema_id}/delete")
def delete_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="delete_schema", min_role="admin", min_level=99999)),
):
    schema_doc = store.schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    store.schema_handler.delete_schema(schema_id)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="schema", resource_id=schema_id, action="delete")
    )
