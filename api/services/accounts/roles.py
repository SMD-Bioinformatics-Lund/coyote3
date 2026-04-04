"""Admin role workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.schemas import normalize_collection_document
from api.extensions import store
from api.http import api_error
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    current_actor,
    inject_version_history,
    lower,
    mutation_payload,
    normalize_managed_form_payload,
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


class RoleManagementService:
    """Role-management workflows for privileged HTTP routes."""

    def __init__(self, repository: Any | None = None) -> None:
        """Build the service with an admin repository."""
        self.repository = repository or store.get_admin_repository()
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

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        """Create context payload.

        Args:
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        form = build_managed_form(self._spec, actor_username=actor_username)
        options = self.repository.list_permission_policy_options()
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        return {"form": form}

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
        form = build_managed_form(self._spec)
        options = self.repository.list_permission_policy_options()
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        form["fields"]["permissions"]["default"] = role.get("permissions")
        form["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")
        return {"role": role, "form": form}

    def create_role(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create role.

        Args:
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        role = normalize_managed_form_payload(self._spec, payload.get("form_data", {}) or {})
        role_id = lower(role.get("name"))
        role.setdefault("is_active", True)
        role["role_id"] = role_id
        existing_role = self.repository.get_role(role_id)
        if isinstance(existing_role, dict) and (
            existing_role.get("role_id") or existing_role.get("_id")
        ):
            raise api_error(409, "Role already exists")
        if role_id in CANONICAL_ROLE_LEVELS:
            role["level"] = CANONICAL_ROLE_LEVELS[role_id]
        actor = current_actor(actor_username)
        role = inject_version_history(actor_username=actor, new_config=role, is_new=True)
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
        updated_role = normalize_managed_form_payload(
            self._spec, payload.get("form_data", {}) or {}
        )
        actor = current_actor(actor_username)
        updated_role["updated_by"] = actor
        updated_role["updated_on"] = utc_now()
        updated_role["version"] = role.get("version", 1) + 1
        updated_role["role_id"] = role.get("role_id", role_id)
        canonical_level = CANONICAL_ROLE_LEVELS.get(updated_role["role_id"])
        if canonical_level is not None:
            updated_role["level"] = canonical_level
        updated_role["_id"] = role.get("_id")
        updated_role = inject_version_history(
            actor_username=actor,
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

    def role_exists(self, *, role_id: str) -> bool:
        """Return whether a role business key already exists."""
        normalized = lower(role_id)
        if not normalized:
            return False
        role = self.repository.get_role(normalized)
        return bool(isinstance(role, dict) and (role.get("role_id") or role.get("_id")))
