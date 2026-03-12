"""Admin permission workflow service."""

from __future__ import annotations

from typing import Any

from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.services.admin_common import current_actor, inject_version_history, mutation_payload, utc_now


class AdminPermissionService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_permissions_payload(self) -> dict[str, Any]:
        permission_policies = self.repository.list_permissions(is_active=False)
        grouped_permissions: dict[str, list[dict[str, Any]]] = {}
        for policy in permission_policies:
            grouped_permissions.setdefault(policy.get("category", "Uncategorized"), []).append(policy)
        return {
            "permission_policies": permission_policies,
            "grouped_permissions": grouped_permissions,
        }

    def create_context_payload(self, *, schema_id: str | None, actor_username: str) -> dict[str, Any]:
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="acl_config",
            schema_category="RBAC",
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, "No active permission schemas found")
        if not selected_schema:
            raise api_error(404, "Selected schema not found")

        schema = self.repository.clone_schema(selected_schema)
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()
        return {"schemas": schemas, "selected_schema": selected_schema, "schema": schema}

    def context_payload(self, *, permission_id: str) -> dict[str, Any]:
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        schema = self.repository.get_schema(permission.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for permission policy")
        return {"permission": permission, "schema": schema}

    def create_permission(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        schemas, schema = self.repository.get_active_schema(
            schema_type="acl_config",
            schema_category="RBAC",
            schema_id=payload.get("schema_id"),
        )
        if not schemas:
            raise api_error(400, "No active permission schemas found")
        if not schema:
            raise api_error(404, "Selected schema not found")

        form_data = payload.get("form_data", {}) or {}
        policy = util.admin.process_form_to_config(form_data, schema)
        policy.setdefault("is_active", True)
        policy_id = str(policy["permission_name"]).strip()
        policy["permission_id"] = policy_id
        policy["_id"] = policy_id
        policy["schema_name"] = schema.get("schema_id") or schema["_id"]
        policy["schema_version"] = schema["version"]
        policy = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=policy,
            is_new=True,
        )
        self.repository.create_permission(policy)
        return mutation_payload(resource="permission", resource_id=policy_id, action="create")

    def update_permission(self, *, permission_id: str, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        schema = self.repository.get_schema(permission.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for permission policy")

        form_data = payload.get("form_data", {}) or {}
        updated_permission = util.admin.process_form_to_config(form_data, schema)
        updated_permission["updated_on"] = utc_now()
        updated_permission["updated_by"] = current_actor(actor_username)
        updated_permission["version"] = permission.get("version", 1) + 1
        updated_permission["schema_name"] = schema.get("schema_id") or schema["_id"]
        updated_permission["permission_id"] = permission.get("permission_id", permission_id)
        updated_permission["_id"] = permission.get("_id")
        updated_permission["schema_version"] = schema["version"]
        updated_permission = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_permission,
            old_config=permission,
            is_new=False,
        )
        self.repository.update_permission(permission_id, updated_permission)
        return mutation_payload(resource="permission", resource_id=permission_id, action="update")

    def toggle_permission(self, *, permission_id: str) -> dict[str, Any]:
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        new_status = not bool(permission.get("is_active", True))
        self.repository.set_permission_active(permission_id, new_status)
        payload = mutation_payload(resource="permission", resource_id=permission_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_permission(self, *, permission_id: str) -> dict[str, Any]:
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        self.repository.delete_permission(permission_id)
        return mutation_payload(resource="permission", resource_id=permission_id, action="delete")
