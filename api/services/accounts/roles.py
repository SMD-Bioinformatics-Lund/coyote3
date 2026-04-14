"""Admin role workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.schemas import normalize_collection_document
from api.http import api_error
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    inject_version_history,
    lower,
    normalize_managed_form_payload,
    normalize_permission_ids,
    utc_now,
)


def _normalize_permission_id(permission_id: Any) -> str:
    """Normalize a permission identifier for UI values."""
    return str(permission_id or "").strip().lower()


CANONICAL_ROLE_LEVELS: dict[str, int] = {
    "external": 1,
    "viewer": 5,
    "intern": 7,
    "user": 9,
    "manager": 99,
    "tester": 999,
    "developer": 9999,
    "admin": 99999,
    "superuser": 1000000,
}


class RoleManagementService:
    """Role-management workflows for privileged HTTP routes."""

    @classmethod
    def from_store(cls, store: Any) -> "RoleManagementService":
        """Build the service from the shared store."""
        return cls(
            roles_handler=store.roles_handler,
            permissions_handler=store.permissions_handler,
        )

    def __init__(
        self,
        *,
        roles_handler: Any,
        permissions_handler: Any,
    ) -> None:
        """Create the service for managed role workflows."""
        self._spec = managed_resource_spec("role")
        self.roles_handler = roles_handler
        self.permissions_handler = permissions_handler

    @staticmethod
    def _normalize_role_permissions(role: dict[str, Any]) -> dict[str, Any]:
        """Return role payload with canonical permission ids."""
        normalized_role = dict(role)
        normalized_role["permissions"] = normalize_permission_ids(
            normalized_role.get("permissions")
        )
        normalized_role["deny_permissions"] = normalize_permission_ids(
            normalized_role.get("deny_permissions")
        )
        return normalized_role

    def list_roles_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """Return the admin list payload for roles.

        Returns:
            dict[str, Any]: Role rows and pagination metadata.
        """
        rows, total = self.roles_handler.search_roles(q=q, page=page, per_page=per_page)
        roles = [
            self._normalize_role_permissions(dict(item)) for item in rows if isinstance(item, dict)
        ]
        return {
            "roles": roles,
            "pagination": admin_list_pagination(
                q=q, page=page, per_page=per_page, total=int(total or 0)
            ),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        """Return form context for creating a role.

        Args:
            actor_username: Username used for default form metadata.

        Returns:
            dict[str, Any]: Form payload for the create view.
        """
        form = build_managed_form(self._spec, actor_username=actor_username)
        options = [
            {
                "value": _normalize_permission_id(p.get("permission_id")),
                "label": p.get("label", _normalize_permission_id(p.get("permission_id"))),
                "category": p.get("category", "Uncategorized"),
            }
            for p in self.permissions_handler.get_all_permissions(is_active=True)
        ]
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        return {"form": form}

    def context_payload(self, *, role_id: str) -> dict[str, Any]:
        """Return form context for editing a role.

        Args:
            role_id: Role identifier to load.

        Returns:
            dict[str, Any]: Existing role data and edit form payload.
        """
        role = self.roles_handler.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        role = self._normalize_role_permissions(role)
        form = build_managed_form(self._spec)
        options = [
            {
                "value": _normalize_permission_id(p.get("permission_id")),
                "label": p.get("label", _normalize_permission_id(p.get("permission_id"))),
                "category": p.get("category", "Uncategorized"),
            }
            for p in self.permissions_handler.get_all_permissions(is_active=True)
        ]
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        form["fields"]["permissions"]["default"] = normalize_permission_ids(role.get("permissions"))
        form["fields"]["deny_permissions"]["default"] = normalize_permission_ids(
            role.get("deny_permissions")
        )
        return {"role": role, "form": form}

    def create_role(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create a new role from submitted form data.

        Args:
            payload: Submitted form payload.
            actor_username: User creating the role.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        role = normalize_managed_form_payload(self._spec, payload.get("form_data", {}) or {})
        role["permissions"] = normalize_permission_ids(role.get("permissions"))
        role["deny_permissions"] = normalize_permission_ids(role.get("deny_permissions"))
        role_id = lower(role.get("name"))
        role.setdefault("is_active", True)
        role["role_id"] = role_id
        existing_role = self.roles_handler.get_role(role_id)
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
        self.roles_handler.create_role(role)
        return change_payload(resource="role", resource_id=role_id, action="create")

    def update_role(
        self, *, role_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update an existing role.

        Args:
            role_id: Role identifier to update.
            payload: Submitted form payload.
            actor_username: User updating the role.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        role = self.roles_handler.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        updated_role = normalize_managed_form_payload(
            self._spec, payload.get("form_data", {}) or {}
        )
        updated_role["permissions"] = normalize_permission_ids(updated_role.get("permissions"))
        updated_role["deny_permissions"] = normalize_permission_ids(
            updated_role.get("deny_permissions")
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
        self.roles_handler.update_role(role_id, updated_role)
        return change_payload(resource="role", resource_id=role_id, action="update")

    def toggle_role(self, *, role_id: str) -> dict[str, Any]:
        """Toggle whether a role is active.

        Args:
            role_id: Role identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        role = self.roles_handler.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        new_status = not bool(role.get("is_active"))
        self.roles_handler.toggle_role_active(role_id, new_status)
        payload = change_payload(resource="role", resource_id=role_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_role(self, *, role_id: str) -> dict[str, Any]:
        """Delete an existing role.

        Args:
            role_id: Role identifier to delete.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        role = self.roles_handler.get_role(role_id)
        if not role:
            raise api_error(404, "Role not found")
        self.roles_handler.delete_role(role_id)
        return change_payload(resource="role", resource_id=role_id, action="delete")

    def role_exists(self, *, role_id: str) -> bool:
        """Return whether a role business key already exists."""
        normalized = lower(role_id)
        if not normalized:
            return False
        role = self.roles_handler.get_role(normalized)
        return bool(isinstance(role, dict) and (role.get("role_id") or role.get("_id")))
