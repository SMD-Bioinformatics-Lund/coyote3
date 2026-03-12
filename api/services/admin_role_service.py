"""Admin role workflow service."""

from __future__ import annotations

from typing import Any

from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.services.management_common import current_actor, inject_version_history, lower, mutation_payload, utc_now


class AdminRoleService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_roles_payload(self) -> dict[str, Any]:
        return {"roles": self.repository.list_roles()}

    def create_context_payload(self, *, schema_id: str | None, actor_username: str) -> dict[str, Any]:
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="rbac_role",
            schema_category="RBAC_role",
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, "No active role schemas found")
        if not selected_schema:
            raise api_error(404, "Selected schema not found")

        schema = self.repository.clone_schema(selected_schema)
        options = self.repository.list_permission_policy_options()
        schema["fields"]["permissions"]["options"] = options
        schema["fields"]["deny_permissions"]["options"] = options
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()

        return {
            "schemas": schemas,
            "selected_schema": selected_schema,
            "schema": schema,
        }

    def context_payload(self, *, role_id: str) -> dict[str, Any]:
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        schema = self.repository.get_schema(role.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for role")

        schema = self.repository.clone_schema(schema)
        options = self.repository.list_permission_policy_options()
        schema["fields"]["permissions"]["options"] = options
        schema["fields"]["deny_permissions"]["options"] = options
        schema["fields"]["permissions"]["default"] = role.get("permissions")
        schema["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")
        return {"role": role, "schema": schema}

    def create_role(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        schemas, schema = self.repository.get_active_schema(
            schema_type="rbac_role",
            schema_category="RBAC_role",
            schema_id=payload.get("schema_id"),
        )
        if not schemas:
            raise api_error(400, "No active role schemas found")
        if not schema:
            raise api_error(404, "Selected schema not found")

        role = util.admin.process_form_to_config(payload.get("form_data", {}) or {}, schema)
        role_id = lower(role.get("name"))
        role.setdefault("is_active", True)
        role["role_id"] = role_id
        role["_id"] = role_id
        role["schema_name"] = schema.get("schema_id") or schema["_id"]
        role["schema_version"] = schema["version"]
        role = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=role,
            is_new=True,
        )
        self.repository.create_role(role)
        return mutation_payload(resource="role", resource_id=role_id, action="create")

    def update_role(self, *, role_id: str, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        schema = self.repository.get_schema(role.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for role")

        updated_role = util.admin.process_form_to_config(payload.get("form_data", {}) or {}, schema)
        updated_role["updated_by"] = current_actor(actor_username)
        updated_role["updated_on"] = utc_now()
        updated_role["schema_name"] = schema.get("schema_id") or schema["_id"]
        updated_role["schema_version"] = schema["version"]
        updated_role["version"] = role.get("version", 1) + 1
        updated_role["role_id"] = role.get("role_id", role_id)
        updated_role["_id"] = role.get("_id")
        updated_role = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_role,
            old_config=role,
            is_new=False,
        )
        self.repository.update_role(role_id, updated_role)
        return mutation_payload(resource="role", resource_id=role_id, action="update")

    def toggle_role(self, *, role_id: str) -> dict[str, Any]:
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        new_status = not bool(role.get("is_active"))
        self.repository.set_role_active(role_id, new_status)
        payload = mutation_payload(resource="role", resource_id=role_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_role(self, *, role_id: str) -> dict[str, Any]:
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        self.repository.delete_role(role_id)
        return mutation_payload(resource="role", resource_id=role_id, action="delete")
