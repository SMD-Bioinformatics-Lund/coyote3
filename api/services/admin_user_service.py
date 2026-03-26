"""Admin user workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_managed_schema, build_managed_schema_bundle
from api.contracts.schemas import normalize_collection_document
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.security.password_flows import issue_password_token_for_user, notify_user_change
from api.services.management_common import (
    admin_list_pagination,
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
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()
        self._spec = managed_resource_spec("user")

    def list_users_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """List users payload.

        Returns:
            dict[str, Any]: The function result.
        """
        users, total = self.repository.search_users(q=q, page=page, per_page=per_page)
        return {
            "users": users,
            "roles": self.repository.get_role_colors(),
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
        """Context payload.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")

        schema = self.repository.clone_schema(build_managed_schema(self._spec))
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

    @staticmethod
    def _changed_user_fields(old_doc: dict[str, Any], new_doc: dict[str, Any]) -> list[str]:
        tracked_keys = [
            "email",
            "role",
            "is_active",
            "permissions",
            "deny_permissions",
            "assay_groups",
            "assays",
            "auth_type",
            "must_change_password",
        ]
        changed: list[str] = []
        for key in tracked_keys:
            if old_doc.get(key) != new_doc.get(key):
                changed.append(key)
        return changed

    def create_user(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        """Create user.

        Args:
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schema = build_managed_schema(self._spec)
        selected_schema_id = payload.get("schema_id")
        if selected_schema_id and selected_schema_id != schema.get("schema_id"):
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
        existing_user = self.repository.get_user(username)
        if isinstance(existing_user, dict) and (
            existing_user.get("username")
            or existing_user.get("user_id")
            or existing_user.get("email")
            or existing_user.get("_id")
        ):
            raise api_error(409, "User already exists")
        email_exists = False
        if hasattr(self.repository, "user_handler"):
            email_exists = bool(self.repository.user_handler.user_exists(email=email))
        if email_exists:
            raise api_error(409, "Email already exists")
        user_data.setdefault("is_active", True)
        user_data["email"] = email
        user_data["username"] = username
        if user_data["auth_type"] == "coyote3" and user_data.get("password"):
            user_data["password"] = util.common.hash_password(user_data["password"])
            user_data["must_change_password"] = bool(form_data.get("must_change_password", True))
        else:
            user_data["password"] = None
            if user_data.get("auth_type") == "coyote3":
                user_data["must_change_password"] = True
        user_data = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=user_data,
            is_new=True,
        )
        try:
            user_data = normalize_collection_document(self._spec.collection, user_data)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.repository.create_user(user_data)
        response = mutation_payload(resource="user", resource_id=username, action="create")
        if user_data.get("auth_type") == "coyote3":
            try:
                invite = issue_password_token_for_user(
                    login_identifier=username,
                    purpose="invite",
                    actor_username=current_actor(actor_username),
                )
                response["meta"]["invite_email_sent"] = bool(invite.get("email_sent", False))
                response["meta"]["mail_configured"] = bool(invite.get("mail_configured", False))
                if invite.get("setup_url"):
                    response["meta"]["invite_setup_url"] = str(invite["setup_url"])
                if invite.get("warning"):
                    response["meta"]["warning"] = str(invite["warning"])
            except RuntimeError:
                # Non-request/unit-test contexts may not have full API runtime bound.
                response["meta"]["invite_email_sent"] = False
                response["meta"]["mail_configured"] = False
                response["meta"][
                    "warning"
                ] = "Invite token/email issuance skipped: API runtime not initialized."
        return response

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
        schema = build_managed_schema(self._spec)

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
        try:
            updated_user = normalize_collection_document(self._spec.collection, updated_user)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.repository.update_user(user_id, updated_user)
        payload = mutation_payload(resource="user", resource_id=user_id, action="update")
        changed_fields = self._changed_user_fields(user_doc, updated_user)
        if form_data.get("password"):
            changed_fields.append("password")
        notification = notify_user_change(
            user_doc=updated_user,
            event="profile_updated",
            actor_username=current_actor(actor_username),
            changed_fields=changed_fields or ["profile"],
        )
        payload["meta"]["change_email_sent"] = bool(notification.get("email_sent", False))
        if notification.get("warning"):
            payload["meta"]["warning"] = str(notification["warning"])
        return payload

    def send_local_user_invite(self, *, user_id: str, actor_username: str) -> dict[str, Any]:
        """Issue and email a local-user set-password invite."""
        user_doc = self.repository.get_user(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        if str(user_doc.get("auth_type") or "coyote3").lower() != "coyote3":
            raise api_error(400, "Invite is only available for local users")

        invite = issue_password_token_for_user(
            login_identifier=str(user_doc.get("username") or user_id),
            purpose="invite",
            actor_username=current_actor(actor_username),
        )
        payload = mutation_payload(resource="user", resource_id=user_id, action="invite")
        payload["meta"]["invite_email_sent"] = bool(invite.get("email_sent", False))
        payload["meta"]["mail_configured"] = bool(invite.get("mail_configured", False))
        if invite.get("setup_url"):
            payload["meta"]["invite_setup_url"] = str(invite["setup_url"])
        if invite.get("warning"):
            payload["meta"]["warning"] = str(invite["warning"])
        return payload

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
        notification = notify_user_change(
            user_doc={**user_doc, "is_active": new_status},
            event="account_status_changed",
            actor_username="admin-ui",
            changed_fields=["is_active"],
        )
        payload["meta"]["change_email_sent"] = bool(notification.get("email_sent", False))
        if notification.get("warning"):
            payload["meta"]["warning"] = str(notification["warning"])
        return payload

    def username_exists(self, *, username: str) -> bool:
        """Username exists.

        Args:
            username (str): Value for ``username``.

        Returns:
            bool: The function result.
        """
        return bool(self.repository.user_handler.user_exists(username=lower(username)))

    def email_exists(self, *, email: str) -> bool:
        """Email exists.

        Args:
            email (str): Value for ``email``.

        Returns:
            bool: The function result.
        """
        return bool(self.repository.user_handler.user_exists(email=lower(email)))
