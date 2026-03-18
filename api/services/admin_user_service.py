"""Admin user workflow service."""

from __future__ import annotations

from typing import Any

from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.services.management_common import (
    current_actor,
    inject_version_history,
    lower,
    mutation_payload,
    role_permission_overrides,
    utc_now,
)


class AdminUserService:
    """Own user-management workflows for admin HTTP routes."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()

    def list_users_payload(self) -> dict[str, Any]:
        """List users payload.

        Returns:
            dict[str, Any]: The function result.
        """
        return {"users": self.repository.list_users(), "roles": self.repository.get_role_colors()}

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
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="rbac_user",
            schema_category="RBAC_user",
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, "No active user schemas found")
        if not selected_schema:
            raise api_error(404, "User schema not found")

        schema = self.repository.clone_schema(selected_schema)
        options = self.repository.list_permission_policy_options()
        schema["fields"]["role"]["options"] = self.repository.get_role_names()
        schema["fields"]["permissions"]["options"] = options
        schema["fields"]["deny_permissions"]["options"] = options
        schema["fields"]["assay_groups"]["options"] = self.repository.get_asp_groups()
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()

        return {
            "schemas": schemas,
            "selected_schema": selected_schema,
            "schema": schema,
            "role_map": self.repository.get_roles_policy_map(),
            "assay_group_map": self.repository.get_assay_group_map(),
        }

    def context_payload(self, *, user_id: str) -> dict[str, Any]:
        """Handle context payload.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")

        schema = self.repository.get_schema(user_doc.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for user")

        schema = self.repository.clone_schema(schema)
        options = self.repository.list_permission_policy_options()
        schema["fields"]["role"]["options"] = self.repository.get_role_names()
        schema["fields"]["permissions"]["options"] = options
        schema["fields"]["deny_permissions"]["options"] = options
        schema["fields"]["permissions"]["default"] = user_doc.get("permissions")
        schema["fields"]["deny_permissions"]["default"] = user_doc.get("deny_permissions")
        schema["fields"]["assay_groups"]["options"] = self.repository.get_asp_groups()
        schema["fields"]["assay_groups"]["default"] = user_doc.get("assay_groups", [])
        schema["fields"]["assays"]["default"] = user_doc.get("assays", [])

        return {
            "user_doc": user_doc,
            "schema": schema,
            "role_map": self.repository.get_roles_policy_map(),
            "assay_group_map": self.repository.get_assay_group_map(),
        }

    def create_user(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create user.

        Args:
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schemas, schema = self.repository.get_active_schema(
            schema_type="rbac_user",
            schema_category="RBAC_user",
            schema_id=payload.get("schema_id"),
        )
        if not schemas:
            raise api_error(400, "No active user schemas found")
        if not schema:
            raise api_error(404, "User schema not found")

        form_data = dict(payload.get("form_data", {}) or {})
        role_map = self.repository.get_roles_policy_map()
        permissions, deny_permissions = role_permission_overrides(
            role_map=role_map,
            role_name=form_data.get("role"),
            permissions=form_data.get("permissions"),
            deny_permissions=form_data.get("deny_permissions"),
        )
        form_data["permissions"] = permissions
        form_data["deny_permissions"] = deny_permissions

        user_data = util.admin.process_form_to_config(form_data, schema)
        username = lower(user_data.get("username"))
        email = lower(user_data.get("email"))
        user_data.setdefault("is_active", True)
        user_data["schema_name"] = schema.get("schema_id")
        user_data["schema_version"] = schema["version"]
        user_data["email"] = email
        user_data["username"] = username
        if user_data["auth_type"] == "coyote3" and user_data.get("password"):
            user_data["password"] = util.common.hash_password(user_data["password"])
        else:
            user_data["password"] = None
        user_data = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=user_data,
            is_new=True,
        )
        self.repository.create_user(user_data)
        return mutation_payload(resource="user", resource_id=username, action="create")

    def update_user(
        self, *, user_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update user.

        Args:
            user_id (str): Value for ``user_id``.
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        schema = self.repository.get_schema(user_doc.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for user")

        form_data = dict(payload.get("form_data", {}) or {})
        updated_user = util.admin.process_form_to_config(form_data, schema)
        role_map = self.repository.get_roles_policy_map()
        permissions, deny_permissions = role_permission_overrides(
            role_map=role_map,
            role_name=updated_user.get("role"),
            permissions=updated_user.get("permissions"),
            deny_permissions=updated_user.get("deny_permissions"),
        )
        updated_user["permissions"] = permissions
        updated_user["deny_permissions"] = deny_permissions
        updated_user["updated_on"] = utc_now()
        updated_user["updated_by"] = current_actor(actor_username)
        if updated_user["auth_type"] == "coyote3" and updated_user.get("password"):
            updated_user["password"] = util.common.hash_password(updated_user["password"])
        else:
            updated_user["password"] = user_doc.get("password")
        updated_user["schema_name"] = schema.get("schema_id")
        updated_user["schema_version"] = schema["version"]
        updated_user["version"] = user_doc.get("version", 1) + 1
        updated_user["_id"] = user_doc.get("_id")
        updated_user["email"] = lower(updated_user.get("email"))
        updated_user["username"] = lower(updated_user.get("username"))
        updated_user = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_user,
            old_config=user_doc,
            is_new=False,
        )
        self.repository.update_user(user_id, updated_user)
        return mutation_payload(resource="user", resource_id=user_id, action="update")

    def delete_user(self, *, user_id: str) -> dict[str, Any]:
        """Delete user.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        self.repository.delete_user(user_id)
        return mutation_payload(resource="user", resource_id=user_id, action="delete")

    def toggle_user(self, *, user_id: str) -> dict[str, Any]:
        """Toggle user.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        new_status = not bool(user_doc.get("is_active"))
        self.repository.set_user_active(user_id, new_status)
        payload = mutation_payload(resource="user", resource_id=user_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def username_exists(self, *, username: str) -> bool:
        """Handle username exists.

        Args:
            username (str): Value for ``username``.

        Returns:
            bool: The function result.
        """
        return bool(self.repository.user_handler.user_exists(username=lower(username)))

    def email_exists(self, *, email: str) -> bool:
        """Handle email exists.

        Args:
            email (str): Value for ``email``.

        Returns:
            bool: The function result.
        """
        return bool(self.repository.user_handler.user_exists(email=lower(email)))
