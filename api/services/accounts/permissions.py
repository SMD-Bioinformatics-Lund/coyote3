"""Permission policy workflow service."""

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
    mutation_payload,
    normalize_managed_form_payload,
    utc_now,
)


class PermissionManagementService:
    """Own permission-policy workflows for admin HTTP routes."""

    def __init__(self, repository: Any | None = None) -> None:
        """Build the service with an admin repository."""
        self.repository = repository or store.get_admin_repository()
        self._spec = managed_resource_spec("permission")

    def list_permissions_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """List permissions payload.

        Returns:
            dict[str, Any]: The function result.
        """
        permission_policies, total = self.repository.search_permissions(
            q=q,
            page=page,
            per_page=per_page,
            is_active=False,
        )
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
        """Create context payload.

        Args:
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        return {"form": build_managed_form(self._spec, actor_username=actor_username)}

    def context_payload(self, *, permission_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            permission_id (str): Value for ``permission_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        return {"permission": permission, "form": build_managed_form(self._spec)}

    def create_permission(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create permission.

        Args:
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        form_data = payload.get("form_data", {}) or {}
        policy = normalize_managed_form_payload(self._spec, form_data)
        policy.setdefault("is_active", True)
        policy_id = str(policy["permission_name"]).strip()
        policy["permission_id"] = policy_id
        existing_policy = self.repository.get_permission(policy_id)
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
        self.repository.create_permission(policy)
        return mutation_payload(resource="permission", resource_id=policy_id, action="create")

    def update_permission(
        self, *, permission_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update permission.

        Args:
            permission_id (str): Value for ``permission_id``.
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        form_data = payload.get("form_data", {}) or {}
        updated_permission = normalize_managed_form_payload(self._spec, form_data)
        actor = current_actor(actor_username)
        updated_permission["updated_on"] = utc_now()
        updated_permission["updated_by"] = actor
        updated_permission["version"] = permission.get("version", 1) + 1
        updated_permission["permission_id"] = permission.get("permission_id", permission_id)
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
        self.repository.update_permission(permission_id, updated_permission)
        return mutation_payload(resource="permission", resource_id=permission_id, action="update")

    def toggle_permission(self, *, permission_id: str) -> dict[str, Any]:
        """Toggle permission.

        Args:
            permission_id (str): Value for ``permission_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        new_status = not bool(permission.get("is_active", True))
        self.repository.set_permission_active(permission_id, new_status)
        payload = mutation_payload(
            resource="permission", resource_id=permission_id, action="toggle"
        )
        payload["meta"]["is_active"] = new_status
        return payload

    def delete_permission(self, *, permission_id: str) -> dict[str, Any]:
        """Delete permission.

        Args:
            permission_id (str): Value for ``permission_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise api_error(404, "Permission policy not found")
        self.repository.delete_permission(permission_id)
        return mutation_payload(resource="permission", resource_id=permission_id, action="delete")

    def permission_exists(self, *, permission_id: str) -> bool:
        """Return whether a permission business key already exists."""
        normalized = str(permission_id or "").strip()
        if not normalized:
            return False
        policy = self.repository.get_permission(normalized)
        return bool(isinstance(policy, dict) and (policy.get("permission_id") or policy.get("_id")))
