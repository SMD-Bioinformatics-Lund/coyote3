"""Permission policy workflow service."""

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
    normalize_managed_form_payload,
    utc_now,
)


def _normalize_permission_id(permission_id: Any) -> str:
    """Normalize a permission identifier for persistence."""
    return str(permission_id or "").strip().lower()


class PermissionManagementService:
    """Own permission-policy workflows for admin HTTP routes."""

    @classmethod
    def from_store(cls, store: Any) -> "PermissionManagementService":
        """Build the service from the shared store."""
        return cls(permissions_handler=store.permissions_handler)

    def __init__(self, *, permissions_handler: Any) -> None:
        """Create the service for managed permission policy workflows."""
        self._spec = managed_resource_spec("permission")
        self.permissions_handler = permissions_handler

    @staticmethod
    def _normalize_permission_policy(policy: dict[str, Any]) -> dict[str, Any]:
        """Return a permission policy with canonical identifiers for UI consumers."""
        normalized_policy = dict(policy)
        canonical_id = _normalize_permission_id(
            normalized_policy.get("permission_id") or normalized_policy.get("permission_name")
        )
        if canonical_id:
            normalized_policy["permission_id"] = canonical_id
            normalized_policy["permission_name"] = canonical_id
        return normalized_policy

    def list_permissions_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """Return the admin list payload for permission policies.

        Returns:
            dict[str, Any]: Permission rows grouped for admin UI rendering.
        """
        rows, total = self.permissions_handler.search_permissions(
            q=q,
            page=page,
            per_page=per_page,
            is_active=False,
        )
        permission_policies = [
            self._normalize_permission_policy(dict(item)) for item in rows if isinstance(item, dict)
        ]
        total = int(total or 0)
        grouped_permissions: dict[str, list[dict[str, Any]]] = {}
        for policy in permission_policies:
            grouped_permissions.setdefault(policy.get("category", "Uncategorized"), []).append(
                policy
            )
        return {
            "permission_policies": permission_policies,
            "grouped_permissions": grouped_permissions,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        """Return form context for creating a permission policy.

        Args:
            actor_username: Username used for default form metadata.

        Returns:
            dict[str, Any]: Form payload for the create view.
        """
        return {"form": build_managed_form(self._spec, actor_username=actor_username)}

    def context_payload(self, *, permission_id: str) -> dict[str, Any]:
        """Return form context for editing a permission policy.

        Args:
            permission_id: Permission identifier to load.

        Returns:
            dict[str, Any]: Existing permission data and edit form payload.
        """
        permission = self.permissions_handler.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        return {
            "permission": self._normalize_permission_policy(permission),
            "form": build_managed_form(self._spec),
        }

    def create_permission(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create a new permission policy from submitted form data.

        Args:
            payload: Submitted form payload.
            actor_username: User creating the permission policy.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        form_data = payload.get("form_data", {}) or {}
        policy = normalize_managed_form_payload(self._spec, form_data)
        policy.setdefault("is_active", True)
        policy_id = _normalize_permission_id(policy["permission_name"])
        policy["permission_name"] = policy_id
        policy["permission_id"] = policy_id
        existing_policy = self.permissions_handler.get_permission(policy_id)
        if isinstance(existing_policy, dict) and (
            existing_policy.get("permission_id") or existing_policy.get("_id")
        ):
            raise api_error(409, "Permission policy already exists")
        actor = current_actor(actor_username)
        policy = inject_version_history(actor_username=actor, new_config=policy, is_new=True)
        try:
            policy = normalize_collection_document(self._spec.collection, policy)
        except Exception as exc:
            raise api_error(400, f"Invalid permission payload: {exc}") from exc
        self.permissions_handler.create_new_policy(policy)
        return change_payload(resource="permission", resource_id=policy_id, action="create")

    def update_permission(
        self, *, permission_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update an existing permission policy.

        Args:
            permission_id: Permission identifier to update.
            payload: Submitted form payload.
            actor_username: User updating the permission policy.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        permission = self.permissions_handler.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        form_data = payload.get("form_data", {}) or {}
        updated_permission = normalize_managed_form_payload(self._spec, form_data)
        actor = current_actor(actor_username)
        updated_permission["updated_on"] = utc_now()
        updated_permission["updated_by"] = actor
        updated_permission["version"] = permission.get("version", 1) + 1
        updated_permission["permission_name"] = str(
            _normalize_permission_id(updated_permission.get("permission_name"))
            or permission.get("permission_id", permission_id)
        )
        updated_permission["permission_id"] = updated_permission["permission_name"]
        updated_permission["_id"] = permission.get("_id")
        updated_permission = inject_version_history(
            actor_username=actor,
            new_config=updated_permission,
            old_config=permission,
            is_new=False,
        )
        try:
            updated_permission = normalize_collection_document(
                self._spec.collection, updated_permission
            )
        except Exception as exc:
            raise api_error(400, f"Invalid permission payload: {exc}") from exc
        self.permissions_handler.update_policy(permission_id, updated_permission)
        return change_payload(resource="permission", resource_id=permission_id, action="update")

    def toggle_permission(self, *, permission_id: str) -> dict[str, Any]:
        """Toggle whether a permission policy is active.

        Args:
            permission_id: Permission identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        permission = self.permissions_handler.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        new_status = not bool(permission.get("is_active", True))
        self.permissions_handler.toggle_policy_active(permission_id, new_status)
        payload = change_payload(resource="permission", resource_id=permission_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_permission(self, *, permission_id: str) -> dict[str, Any]:
        """Delete an existing permission policy.

        Args:
            permission_id: Permission identifier to delete.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        permission = self.permissions_handler.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        self.permissions_handler.delete_policy(permission_id)
        return change_payload(resource="permission", resource_id=permission_id, action="delete")

    def permission_exists(self, *, permission_id: str) -> bool:
        """Return whether a permission business key already exists."""
        normalized = str(permission_id or "").strip()
        if not normalized:
            return False
        policy = self.permissions_handler.get_permission(normalized)
        return bool(isinstance(policy, dict) and (policy.get("permission_id") or policy.get("_id")))
