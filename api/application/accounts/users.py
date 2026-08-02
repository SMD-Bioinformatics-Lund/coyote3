"""Admin user workflow service."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from api.application.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    lower,
    normalize_managed_form_payload,
    normalize_permission_ids,
    utc_now,
)
from api.config.constants import (
    AUTH_PROVIDER_LOCAL,
    DEFAULT_AUTH_PROVIDER,
    normalize_auth_types,
)
from api.contracts.managed_resources import managed_resource_spec
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error
from api.security.password_flows import issue_password_token_for_user, notify_user_change


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


def _normalize_allowed_auth_types(value: Any) -> list[str]:
    """Validate the explicitly selected authentication providers."""
    return [str(provider) for provider in normalize_auth_types(value)]


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
        """Build the service from the runtime store."""
        return cls(
            user_repository=store.user_repository,
            roles_repository=store.roles_repository,
            permissions_repository=store.permissions_repository,
            assay_panel_repository=store.assay_panel_repository,
            common_util=common_util,
        )

    def __init__(
        self,
        *,
        user_repository: Any,
        roles_repository: Any,
        permissions_repository: Any,
        assay_panel_repository: Any,
        common_util: Any,
    ) -> None:
        """Create the service for managed user workflows."""
        self._spec = managed_resource_spec("user")
        self.user_repository = user_repository
        self.roles_repository = roles_repository
        self.permissions_repository = permissions_repository
        self.assay_panel_repository = assay_panel_repository
        self._common_util = common_util

    @staticmethod
    def _normalize_user_permissions(user_doc: dict[str, Any]) -> dict[str, Any]:
        """Return a user payload with canonical permission ids."""
        normalized_user = dict(user_doc)
        normalized_user["roles"] = _normalize_role_ids(normalized_user.get("roles"))
        normalized_user["primary_role"] = (
            normalized_user["roles"][0] if normalized_user["roles"] else ""
        )
        return normalized_user

    def _roles_policy_map(self) -> dict[str, dict[str, Any]]:
        """Build role→policy map from all roles."""
        return {
            role["role_id"]: {
                "permissions": normalize_permission_ids(role.get("permissions", [])),
                "level": role.get("level", 0),
                "color": role.get("color", "gray"),
            }
            for role in (self.roles_repository.get_all_roles() or [])
            if isinstance(role, dict) and role.get("role_id")
        }

    @property
    def common_util(self) -> Any:
        """Return the injected common util helper."""
        return self._common_util

    def list_users_payload(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        users, total = self.user_repository.search_users(q=q, page=page, per_page=per_page)
        users = [
            self._normalize_user_permissions(dict(item)) for item in users if isinstance(item, dict)
        ]
        return {
            "users": users,
            "roles": self.roles_repository.get_role_colors(),
            "pagination": admin_list_pagination(
                q=q, page=page, per_page=per_page, total=int(total or 0)
            ),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        form = build_managed_form(self._spec, actor_username=actor_username)
        role_options = list(self.roles_repository.get_all_role_names() or [])
        form["fields"]["roles"]["options"] = role_options
        if "user" in role_options:
            form["fields"]["roles"]["default"] = ["user"]

        return {
            "form": form,
            "role_map": self._roles_policy_map(),
            "assay_group_map": self.common_util.create_assay_group_map(
                self.assay_panel_repository.get_all_asps()
            ),
        }

    def context_payload(self, *, user_id: str) -> dict[str, Any]:
        user_doc = self.user_repository.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        user_doc = self._normalize_user_permissions(user_doc)

        form = build_managed_form(self._spec)
        role_options = list(self.roles_repository.get_all_role_names() or [])
        form["fields"]["roles"]["options"] = role_options
        form["fields"]["roles"]["default"] = _normalize_role_ids(user_doc.get("roles"))
        form["fields"]["asp_groups"]["default"] = user_doc.get("asp_groups", [])
        form["fields"]["asp_ids"]["default"] = user_doc.get("asp_ids", [])

        return {
            "user_doc": user_doc,
            "form": form,
            "role_map": self._roles_policy_map(),
            "assay_group_map": self.common_util.create_assay_group_map(
                self.assay_panel_repository.get_all_asps()
            ),
        }

    @staticmethod
    def _changed_user_fields(old_doc: dict[str, Any], new_doc: dict[str, Any]) -> list[str]:
        tracked_keys = [
            "email",
            "roles",
            "is_active",
            "asp_groups",
            "asp_ids",
            "auth_type",
            "must_change_password",
        ]
        changed: list[str] = []
        for key in tracked_keys:
            if old_doc.get(key) != new_doc.get(key):
                changed.append(key)
        return changed

    def create_user(
        self,
        *,
        payload: dict[str, Any],
        actor_username: str,
        actor_is_superuser: bool = False,
    ) -> dict[str, Any]:
        form_data = dict(payload.get("form_data", {}) or {})
        form_data["roles"] = _normalize_role_ids(form_data.get("roles"))
        if not form_data["roles"]:
            raise api_error(400, "At least one role is required")
        if "superuser" in form_data["roles"] and not actor_is_superuser:
            raise api_error(403, "Only a superuser may assign the superuser role")

        user_data = normalize_managed_form_payload(self._spec, form_data)
        username = _sanitize_username(user_data.get("username"))
        email = lower(user_data.get("email"))
        if not username:
            raise api_error(400, "Username is required")
        existing_user = self.user_repository.user_with_id(username)
        if isinstance(existing_user, dict) and (
            existing_user.get("username") or existing_user.get("email") or existing_user.get("_id")
        ):
            raise api_error(409, "User already exists")
        if self.user_repository.user_exists(email=email):
            raise api_error(409, "Email already exists")
        user_data.setdefault("is_active", True)
        user_data["email"] = email
        user_data["username"] = username
        user_data["auth_type"] = _normalize_allowed_auth_types(user_data.get("auth_type"))
        if AUTH_PROVIDER_LOCAL in user_data["auth_type"] and user_data.get("password"):
            user_data["password"] = self.common_util.hash_password(user_data["password"])
            user_data["must_change_password"] = bool(form_data.get("must_change_password", True))
        else:
            user_data["password"] = None
            if AUTH_PROVIDER_LOCAL in user_data.get("auth_type", []):
                user_data["must_change_password"] = True
        actor = current_actor(actor_username)
        now = utc_now()
        user_data["version"] = 1
        user_data["created_by"] = actor
        user_data["created_on"] = now
        user_data["updated_by"] = actor
        user_data["updated_on"] = now
        try:
            user_data = normalize_collection_document(self._spec.collection, user_data)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.user_repository.create_user(user_data)
        response: dict[str, Any] = change_payload(
            resource="user", resource_id=username, action="create"
        )
        if AUTH_PROVIDER_LOCAL in user_data.get("auth_type", []):
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
        self,
        *,
        user_id: str,
        payload: dict[str, Any],
        actor_username: str,
        actor_is_superuser: bool = False,
    ) -> dict[str, Any]:
        user_doc = self.user_repository.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        form_data = dict(payload.get("form_data", {}) or {})
        if form_data.get("password"):
            raise api_error(
                400,
                "Passwords cannot be changed from user administration",
                hint="Use an invite, password reset, or the authenticated profile password flow.",
            )
        form_data.pop("password", None)
        form_data["roles"] = _normalize_role_ids(form_data.get("roles"))
        if not form_data["roles"]:
            form_data["roles"] = _normalize_role_ids(user_doc.get("roles"))
        if not form_data["roles"]:
            raise api_error(400, "At least one role is required")
        old_roles = set(_normalize_role_ids(user_doc.get("roles")))
        new_roles = set(form_data["roles"])
        if "superuser" in old_roles.symmetric_difference(new_roles) and not actor_is_superuser:
            raise api_error(403, "Only a superuser may assign or remove the superuser role")
        updated_user = normalize_managed_form_payload(self._spec, form_data)
        actor = current_actor(actor_username)
        updated_user["updated_on"] = utc_now()
        updated_user["updated_by"] = actor
        updated_user["auth_type"] = _normalize_allowed_auth_types(
            updated_user.get("auth_type") or user_doc.get("auth_type")
        )
        updated_user["password"] = user_doc.get("password")
        updated_user["version"] = user_doc.get("version", 1) + 1
        updated_user["_id"] = user_doc.get("_id")
        updated_user["created_by"] = user_doc.get("created_by")
        updated_user["created_on"] = user_doc.get("created_on")
        updated_user["email"] = lower(updated_user.get("email"))
        updated_user["username"] = str(user_doc.get("username") or user_id).strip().lower()
        try:
            updated_user = normalize_collection_document(self._spec.collection, updated_user)
        except Exception as exc:
            raise api_error(400, f"Invalid user payload: {exc}") from exc
        self.user_repository.update_user(user_id, updated_user)
        response: dict[str, Any] = change_payload(
            resource="user", resource_id=user_id, action="update"
        )
        changed_fields = self._changed_user_fields(user_doc, updated_user)
        notification = notify_user_change(
            user_doc=updated_user,
            event="profile_updated",
            actor_username=actor,
            changed_fields=changed_fields or ["user"],
        )
        response["meta"]["change_email_sent"] = bool(notification.get("email_sent", False))
        if notification.get("warning"):
            response["meta"]["warning"] = str(notification["warning"])
        return response

    def update_own_profile(self, *, username: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update only non-security identity fields on the current account."""
        user_doc = self.user_repository.user_with_id(username)
        if not user_doc:
            raise api_error(404, "User not found")
        allowed = {"firstname", "lastname", "fullname", "job_title"}
        unexpected = sorted(set(payload) - allowed)
        if unexpected:
            raise api_error(400, f"Profile field(s) cannot be edited: {', '.join(unexpected)}")
        updated_user = dict(user_doc)
        for field in allowed:
            if field in payload:
                updated_user[field] = str(payload[field] or "").strip()
        if not updated_user.get("fullname"):
            updated_user["fullname"] = " ".join(
                value
                for value in (
                    updated_user.get("firstname", ""),
                    updated_user.get("lastname", ""),
                )
                if value
            )
        updated_user["version"] = int(user_doc.get("version", 1) or 1) + 1
        updated_user["updated_by"] = str(username).strip().lower()
        updated_user["updated_on"] = utc_now()
        try:
            updated_user = normalize_collection_document(self._spec.collection, updated_user)
        except Exception as exc:
            raise api_error(400, f"Invalid profile payload: {exc}") from exc
        self.user_repository.update_user(username, updated_user)
        return {
            "status": "ok",
            "user": {
                "username": updated_user["username"],
                "email": updated_user["email"],
                "firstname": updated_user["firstname"],
                "lastname": updated_user["lastname"],
                "fullname": updated_user["fullname"],
                "job_title": updated_user["job_title"],
            },
        }

    def send_local_user_invite(self, *, user_id: str, actor_username: str) -> dict[str, Any]:
        """Issue and email a local-user set-password invite."""
        user_doc = self.user_repository.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        if AUTH_PROVIDER_LOCAL not in normalize_auth_types(
            user_doc.get("auth_type") or [DEFAULT_AUTH_PROVIDER]
        ):
            raise api_error(400, "Invite is only available for local users")

        invite = issue_password_token_for_user(
            login_identifier=str(user_doc.get("username") or user_id),
            purpose="invite",
            actor_username=current_actor(actor_username),
        )
        payload: dict[str, Any] = change_payload(
            resource="user", resource_id=user_id, action="invite"
        )
        payload["meta"]["invite_email_sent"] = bool(invite.get("email_sent", False))
        payload["meta"]["mail_configured"] = bool(invite.get("mail_configured", False))
        if invite.get("setup_url"):
            payload["meta"]["invite_setup_url"] = str(invite["setup_url"])
        if invite.get("warning"):
            payload["meta"]["warning"] = str(invite["warning"])
        return payload

    def delete_user(self, *, user_id: str, actor_is_superuser: bool = False) -> dict[str, Any]:
        user_doc = self.user_repository.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        if "superuser" in _normalize_role_ids(user_doc.get("roles")) and not actor_is_superuser:
            raise api_error(403, "Only a superuser may delete a superuser account")
        self.user_repository.delete_user(user_id)
        payload: dict[str, Any] = change_payload(
            resource="user", resource_id=user_id, action="delete"
        )
        return payload

    def toggle_user(self, *, user_id: str, actor_is_superuser: bool = False) -> dict[str, Any]:
        user_doc = self.user_repository.user_with_id(user_id)
        if not user_doc:
            raise api_error(404, "User not found")
        if "superuser" in _normalize_role_ids(user_doc.get("roles")) and not actor_is_superuser:
            raise api_error(403, "Only a superuser may change a superuser account status")
        new_status = not bool(user_doc.get("is_active"))
        self.user_repository.toggle_user_active(user_id, new_status)
        payload: dict[str, Any] = change_payload(
            resource="user", resource_id=user_id, action="toggle"
        )
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
        return bool(self.user_repository.user_exists(username=lower(username)))

    def email_exists(self, *, email: str) -> bool:
        return bool(self.user_repository.user_exists(email=lower(email)))
