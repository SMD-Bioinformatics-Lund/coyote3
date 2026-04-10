"""Admin user workflow service."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.schemas import normalize_collection_document
from api.http import api_error
from api.security.password_flows import issue_password_token_for_user, notify_user_change
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    inject_version_history,
    lower,
    normalize_managed_form_payload,
    normalize_permission_ids,
    role_permission_overrides,
    utc_now,
)


def _normalize_permission_id(permission_id: Any) -> str:
    """Normalize a permission identifier for UI values."""
    return str(permission_id or "").strip().lower()


def _normalize_role_ids(role_ids: Any) -> list[str]:
    """Normalize a role-id collection to unique canonical values."""
    normalized: list[str] = []
    seen: set[str] = set()
    if role_ids is None:
        return normalized
    if isinstance(role_ids, (str, bytes)):
        role_ids = [role_ids]
    for role_id in role_ids:
        normalized_id = str(role_id or "").strip().lower()
        if normalized_id and normalized_id not in seen:
            normalized.append(normalized_id)
            seen.add(normalized_id)
    return normalized


def _sanitize_username(value: Any) -> str:
    """Convert a human-entered username into a canonical login id."""
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", ".", ascii_only.strip().lower())
    cleaned = re.sub(r"[._-]{2,}", ".", cleaned).strip("._-")
    return cleaned


class UserManagementService:
    """User-management workflows for privileged HTTP routes."""

    @classmethod
    def from_store(cls, store: Any, *, common_util: Any) -> "UserManagementService":
        """Build the service from the shared store."""
        return cls(
            user_handler=store.user_handler,
            roles_handler=store.roles_handler,
            permissions_handler=store.permissions_handler,
            assay_panel_handler=store.assay_panel_handler,
            common_util=common_util,
        )

    def __init__(
        self,
        *,
        user_handler: Any,
        roles_handler: Any,
        permissions_handler: Any,
        assay_panel_handler: Any,
        common_util: Any,
    ) -> None:
        """Create the service for managed user workflows."""
        self._spec = managed_resource_spec("user")
        self.user_handler = user_handler
        self.roles_handler = roles_handler
        self.permissions_handler = permissions_handler
        self.assay_panel_handler = assay_panel_handler
        self._common_util = common_util

    @staticmethod
    def _normalize_user_permissions(user_doc: dict[str, Any]) -> dict[str, Any]:
        """Return a user payload with canonical permission ids."""
        normalized_user = dict(user_doc)
        normalized_user["roles"] = _normalize_role_ids(normalized_user.get("roles"))
        normalized_user["permissions"] = normalize_permission_ids(
            normalized_user.get("permissions")
        )
        normalized_user["deny_permissions"] = normalize_permission_ids(
            normalized_user.get("deny_permissions")
        )
        normalized_user["primary_role"] = (
            normalized_user["roles"][0] if normalized_user["roles"] else ""
        )
        return normalized_user

    def _permission_policy_options(self) -> list[dict[str, Any]]:
        """Build permission-policy select options from active policies."""
        return [
            {
                "value": _normalize_permission_id(p.get("permission_id")),
                "label": p.get("label", _normalize_permission_id(p.get("permission_id"))),
                "category": p.get("category", "Uncategorized"),
            }
            for p in self.permissions_handler.get_all_permissions(is_active=True)
        ]

    def _roles_policy_map(self) -> dict[str, dict[str, Any]]:
        """Build role→policy map from all roles."""
        return {
            role["role_id"]: {
                "permissions": normalize_permission_ids(role.get("permissions", [])),
                "deny_permissions": normalize_permission_ids(role.get("deny_permissions", [])),
                "level": role.get("level", 0),
                "color": role.get("color", "gray"),
            }
            for role in (self.roles_handler.get_all_roles() or [])
            if isinstance(role, dict) and role.get("role_id")
        }

    @property
    def common_util(self):
        """Return the injected common util helper."""
        return self._common_util

    def list_users_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        users, total = self.user_handler.search_users(q=q, page=page, per_page=per_page)
        users = [
            self._normalize_user_permissions(dict(item)) for item in users if isinstance(item, dict)
        ]
        return {
            "users": users,
            "roles": self.roles_handler.get_role_colors(),
            "pagination": admin_list_pagination(
                q=q, page=page, per_page=per_page, total=int(total or 0)
            ),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        form = build_managed_form(self._spec, actor_username=actor_username)
        options = self._permission_policy_options()
        role_options = list(self.roles_handler.get_all_role_names() or [])
        form["fields"]["roles"]["options"] = role_options
        if "user" in role_options:
            form["fields"]["roles"]["default"] = ["user"]
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        form["fields"]["assay_groups"]["options"] = list(
            self.assay_panel_handler.get_all_asp_groups() or []
        )

        return {
            "form": form,
            "role_map": self._roles_policy_map(),
            "assay_group_map": self.common_util.create_assay_group_map(
                self.assay_panel_handler.get_all_asps()
            ),
        }

    def context_payload(self, *, user_id: str) -> dict[str, Any]:
        user_doc = self.user_handler.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        user_doc = self._normalize_user_permissions(user_doc)

        form = build_managed_form(self._spec)
        options = self._permission_policy_options()
        role_options = list(self.roles_handler.get_all_role_names() or [])
        form["fields"]["roles"]["options"] = role_options
        form["fields"]["roles"]["default"] = _normalize_role_ids(user_doc.get("roles"))
        form["fields"]["permissions"]["options"] = options
        form["fields"]["deny_permissions"]["options"] = options
        form["fields"]["permissions"]["default"] = normalize_permission_ids(
            user_doc.get("permissions")
        )
        form["fields"]["deny_permissions"]["default"] = normalize_permission_ids(
            user_doc.get("deny_permissions")
        )
        form["fields"]["assay_groups"]["options"] = list(
            self.assay_panel_handler.get_all_asp_groups() or []
        )
        form["fields"]["assay_groups"]["default"] = user_doc.get("assay_groups", [])
        form["fields"]["assays"]["default"] = user_doc.get("assays", [])

        return {
            "user_doc": user_doc,
            "form": form,
            "role_map": self._roles_policy_map(),
            "assay_group_map": self.common_util.create_assay_group_map(
                self.assay_panel_handler.get_all_asps()
            ),
        }

    @staticmethod
    def _changed_user_fields(old_doc: dict[str, Any], new_doc: dict[str, Any]) -> list[str]:
        tracked_keys = [
            "email",
            "roles",
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
        form_data = dict(payload.get("form_data", {}) or {})
        form_data["roles"] = _normalize_role_ids(form_data.get("roles"))
        form_data["permissions"] = normalize_permission_ids(form_data.get("permissions"))
        form_data["deny_permissions"] = normalize_permission_ids(form_data.get("deny_permissions"))
        if not form_data["roles"]:
            raise api_error(400, "At least one role is required")
        role_map = self._roles_policy_map()
        permissions, deny_permissions = role_permission_overrides(
            role_map=role_map,
            role_names=form_data.get("roles"),
            permissions=form_data.get("permissions"),
            deny_permissions=form_data.get("deny_permissions"),
        )
        form_data["permissions"] = permissions
        form_data["deny_permissions"] = deny_permissions

        user_data = normalize_managed_form_payload(self._spec, form_data)
        username = _sanitize_username(user_data.get("username"))
        email = lower(user_data.get("email"))
        if not username:
            raise api_error(400, "Username is required")
        existing_user = self.user_handler.user_with_id(username)
        if isinstance(existing_user, dict) and (
            existing_user.get("username") or existing_user.get("email") or existing_user.get("_id")
        ):
            raise api_error(409, "User already exists")
        if self.user_handler.user_exists(email=email):
            raise api_error(409, "Email already exists")
        user_data.setdefault("is_active", True)
        user_data["email"] = email
        user_data["username"] = username
        if user_data["auth_type"] == "coyote3" and user_data.get("password"):
            user_data["password"] = self.common_util.hash_password(user_data["password"])
            user_data["must_change_password"] = bool(form_data.get("must_change_password", True))
        else:
            user_data["password"] = None
            if user_data.get("auth_type") == "coyote3":
                user_data["must_change_password"] = True
        actor = current_actor(actor_username)
        now = utc_now()
        user_data["version"] = 1
        user_data["created_by"] = actor
        user_data["created_on"] = now
        user_data["updated_by"] = actor
        user_data["updated_on"] = now
        user_data = inject_version_history(actor_username=actor, new_config=user_data, is_new=True)
        try:
            user_data = normalize_collection_document(self._spec.collection, user_data)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.user_handler.create_user(user_data)
        response = change_payload(resource="user", resource_id=username, action="create")
        if user_data.get("auth_type") == "coyote3":
            try:
                invite = issue_password_token_for_user(
                    login_identifier=username,
                    purpose="invite",
                    actor_username=actor,
                )
                response["meta"]["invite_email_sent"] = bool(invite.get("email_sent", False))
                response["meta"]["mail_configured"] = bool(invite.get("mail_configured", False))
                if invite.get("setup_url"):
                    response["meta"]["invite_setup_url"] = str(invite["setup_url"])
                if invite.get("warning"):
                    response["meta"]["warning"] = str(invite["warning"])
            except RuntimeError:
                response["meta"]["invite_email_sent"] = False
                response["meta"]["mail_configured"] = False
                response["meta"]["warning"] = (
                    "Invite token/email issuance skipped: API runtime not initialized."
                )
        return response

    def update_user(
        self, *, user_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        user_doc = self.user_handler.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        form_data = dict(payload.get("form_data", {}) or {})
        form_data["roles"] = _normalize_role_ids(form_data.get("roles"))
        if not form_data["roles"]:
            form_data["roles"] = _normalize_role_ids(user_doc.get("roles"))
        form_data["permissions"] = normalize_permission_ids(form_data.get("permissions"))
        form_data["deny_permissions"] = normalize_permission_ids(form_data.get("deny_permissions"))
        if not form_data["roles"]:
            raise api_error(400, "At least one role is required")
        updated_user = normalize_managed_form_payload(self._spec, form_data)
        role_map = self._roles_policy_map()
        permissions, deny_permissions = role_permission_overrides(
            role_map=role_map,
            role_names=updated_user.get("roles"),
            permissions=updated_user.get("permissions"),
            deny_permissions=updated_user.get("deny_permissions"),
        )
        updated_user["permissions"] = permissions
        updated_user["deny_permissions"] = deny_permissions
        actor = current_actor(actor_username)
        updated_user["updated_on"] = utc_now()
        updated_user["updated_by"] = actor
        if updated_user["auth_type"] == "coyote3" and updated_user.get("password"):
            updated_user["password"] = self.common_util.hash_password(updated_user["password"])
        else:
            updated_user["password"] = user_doc.get("password")
        updated_user["version"] = user_doc.get("version", 1) + 1
        updated_user["_id"] = user_doc.get("_id")
        updated_user["created_by"] = user_doc.get("created_by")
        updated_user["created_on"] = user_doc.get("created_on")
        updated_user["email"] = lower(updated_user.get("email"))
        updated_user["username"] = str(user_doc.get("username") or user_id).strip().lower()
        updated_user = inject_version_history(
            actor_username=actor,
            new_config=updated_user,
            old_config=user_doc,
            is_new=False,
        )
        try:
            updated_user = normalize_collection_document(self._spec.collection, updated_user)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.user_handler.update_user(user_id, updated_user)
        payload = change_payload(resource="user", resource_id=user_id, action="update")
        changed_fields = self._changed_user_fields(user_doc, updated_user)
        if form_data.get("password"):
            changed_fields.append("password")
        notification = notify_user_change(
            user_doc=updated_user,
            event="profile_updated",
            actor_username=actor,
            changed_fields=changed_fields or ["profile"],
        )
        payload["meta"]["change_email_sent"] = bool(notification.get("email_sent", False))
        if notification.get("warning"):
            payload["meta"]["warning"] = str(notification["warning"])
        return payload

    def send_local_user_invite(self, *, user_id: str, actor_username: str) -> dict[str, Any]:
        """Issue and email a local-user set-password invite."""
        user_doc = self.user_handler.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        if str(user_doc.get("auth_type") or "coyote3").lower() != "coyote3":
            raise api_error(400, "Invite is only available for local users")

        invite = issue_password_token_for_user(
            login_identifier=str(user_doc.get("username") or user_id),
            purpose="invite",
            actor_username=current_actor(actor_username),
        )
        payload = change_payload(resource="user", resource_id=user_id, action="invite")
        payload["meta"]["invite_email_sent"] = bool(invite.get("email_sent", False))
        payload["meta"]["mail_configured"] = bool(invite.get("mail_configured", False))
        if invite.get("setup_url"):
            payload["meta"]["invite_setup_url"] = str(invite["setup_url"])
        if invite.get("warning"):
            payload["meta"]["warning"] = str(invite["warning"])
        return payload

    def delete_user(self, *, user_id: str) -> dict[str, Any]:
        user_doc = self.user_handler.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        self.user_handler.delete_user(user_id)
        return change_payload(resource="user", resource_id=user_id, action="delete")

    def toggle_user(self, *, user_id: str) -> dict[str, Any]:
        user_doc = self.user_handler.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        new_status = not bool(user_doc.get("is_active"))
        self.user_handler.toggle_user_active(user_id, new_status)
        payload = change_payload(resource="user", resource_id=user_id, action="toggle")
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
        return bool(self.user_handler.user_exists(username=lower(username)))

    def email_exists(self, *, email: str) -> bool:
        return bool(self.user_handler.user_exists(email=lower(email)))
