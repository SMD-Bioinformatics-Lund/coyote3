"""Admin role workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_managed_schema, build_managed_schema_bundle
from api.contracts.schemas import normalize_collection_document
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.services.management_common import (
    admin_list_pagination,
    current_actor,
    inject_version_history,
    lower,
    mutation_payload,
    utc_now,
)

CANONICAL_ROLE_LEVELS: dict[str, int] = {
    "external": 1,
    "viewer": 5,
    "intern": 7,
    "user": 9,
    "manager": 99,
    "developer": 9999,
    "admin": 99999,
}


class AdminRoleService:
    """Own role-management workflows for admin HTTP routes."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()
        self._spec = managed_resource_spec("role")

    def list_roles_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """List roles payload.

        Returns:
            dict[str, Any]: The function result.
        """
        roles, total = self.repository.search_roles(q=q, page=page, per_page=per_page)
        return {
            "roles": roles,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(
        self, *, schema_id: str | None, actor_username: str
    ) -> dict[str, Any]:
        """Create context payload.

        Args:
            schema_id (str | None): Value for ``schema_id``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schemas, selected_schema = build_managed_schema_bundle(self._spec)
        if schema_id and schema_id != selected_schema.get("schema_id"):
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
        """Context payload.

        Args:
            role_id (str): Value for ``role_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        schema = self.repository.clone_schema(build_managed_schema(self._spec))
        options = self.repository.list_permission_policy_options()
        schema["fields"]["permissions"]["options"] = options
        schema["fields"]["deny_permissions"]["options"] = options
        schema["fields"]["permissions"]["default"] = role.get("permissions")
        schema["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")
        return {"role": role, "schema": schema}

    def create_role(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create role.

        Args:
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schema = build_managed_schema(self._spec)
        selected_schema_id = payload.get("schema_id")
        if selected_schema_id and selected_schema_id != schema.get("schema_id"):
            raise api_error(404, "Selected schema not found")

        role = util.admin.process_form_to_config(payload.get("form_data", {}) or {}, schema)
        role_id = lower(role.get("name"))
        role.setdefault("is_active", True)
        role["role_id"] = role_id
        if role_id in CANONICAL_ROLE_LEVELS:
            role["level"] = CANONICAL_ROLE_LEVELS[role_id]
        role = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=role,
            is_new=True,
        )
        try:
            role = normalize_collection_document(self._spec.collection, role)
        except Exception as exc:
            raise api_error(400, f"Invalid role payload: {exc}") from exc
        self.repository.create_role(role)
        return mutation_payload(resource="role", resource_id=role_id, action="create")

    def update_role(
        self, *, role_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update role.

        Args:
            role_id (str): Value for ``role_id``.
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        schema = build_managed_schema(self._spec)

        updated_role = util.admin.process_form_to_config(payload.get("form_data", {}) or {}, schema)
        updated_role["updated_by"] = current_actor(actor_username)
        updated_role["updated_on"] = utc_now()
        updated_role["version"] = role.get("version", 1) + 1
        updated_role["role_id"] = role.get("role_id", role_id)
        canonical_level = CANONICAL_ROLE_LEVELS.get(updated_role["role_id"])
        if canonical_level is not None:
            updated_role["level"] = canonical_level
        updated_role["_id"] = role.get("_id")
        updated_role = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_role,
            old_config=role,
            is_new=False,
        )
        try:
            updated_role = normalize_collection_document(self._spec.collection, updated_role)
        except Exception as exc:
            raise api_error(400, f"Invalid role payload: {exc}") from exc
        self.repository.update_role(role_id, updated_role)
        return mutation_payload(resource="role", resource_id=role_id, action="update")

    def toggle_role(self, *, role_id: str) -> dict[str, Any]:
        """Toggle role.

        Args:
            role_id (str): Value for ``role_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        new_status = not bool(role.get("is_active"))
        self.repository.set_role_active(role_id, new_status)
        payload = mutation_payload(resource="role", resource_id=role_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_role(self, *, role_id: str) -> dict[str, Any]:
        """Delete role.

        Args:
            role_id (str): Value for ``role_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        role = self.repository.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        self.repository.delete_role(role_id)
        return mutation_payload(resource="role", resource_id=role_id, action="delete")
