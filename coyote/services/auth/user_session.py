"""Web session user model for Flask-Login.

This module is web-owned and intentionally avoids importing API internals.
It stores only the fields needed by Flask routes and templates.
"""

from __future__ import annotations

from typing import Any

from flask_login import UserMixin


def _unique_permission_ids(permission_ids: list[str] | None) -> list[str]:
    """Normalize and deduplicate permission ids read from session payloads."""
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for permission_id in permission_ids or []:
        value = str(permission_id or "").strip().lower()
        if value and value not in seen:
            normalized_ids.append(value)
            seen.add(value)
    return normalized_ids


def _unique_role_ids(role_ids: list[str] | None) -> list[str]:
    """Normalize and deduplicate role ids read from session payloads."""
    normalized_roles: list[str] = []
    seen: set[str] = set()
    for role_id in role_ids or []:
        value = str(role_id or "").strip().lower()
        if value and value not in seen:
            normalized_roles.append(value)
            seen.add(value)
    return normalized_roles


class SessionUserModel:
    """Minimal session user payload used by the web app.

    Args:
        payload: User dictionary returned by API auth endpoints.
    """

    def __init__(self, payload: dict[str, Any]):
        """__init__.

        Args:
                payload: Payload.
        """
        self.id = str(payload.get("username") or payload.get("_id") or payload.get("id") or "")
        self.email = str(payload.get("email") or "")
        self.fullname = str(payload.get("fullname") or "")
        self.username = str(payload.get("username") or "")
        self.roles = _unique_role_ids(payload.get("roles") or [])
        self.role = str(payload.get("role") or (self.roles[0] if self.roles else ""))
        self.access_level = int(payload.get("access_level") or 0)
        self.permissions = _unique_permission_ids(payload.get("permissions") or [])
        self.denied_permissions = _unique_permission_ids(payload.get("denied_permissions") or [])
        self.assays = list(payload.get("assays") or [])
        self.assay_groups = list(payload.get("assay_groups") or [])
        self.envs = list(payload.get("envs") or [])
        self.asp_map = dict(payload.get("asp_map") or {})
        self.auth_type = str(payload.get("auth_type") or "coyote3")
        self.must_change_password = bool(payload.get("must_change_password") or False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize user fields into a JSON-safe dict for session storage."""
        return {
            "_id": self.username,
            "email": self.email,
            "fullname": self.fullname,
            "username": self.username,
            "roles": list(self.roles),
            "role": self.role,
            "access_level": self.access_level,
            "permissions": list(self.permissions),
            "denied_permissions": list(self.denied_permissions),
            "assays": list(self.assays),
            "assay_groups": list(self.assay_groups),
            "envs": list(self.envs),
            "asp_map": dict(self.asp_map),
            "auth_type": self.auth_type,
            "must_change_password": bool(self.must_change_password),
        }


class User(UserMixin):
    """Flask-Login user wrapper backed by :class:`SessionUserModel`."""

    def __init__(self, user_model: SessionUserModel | dict[str, Any]):
        """__init__.

        Args:
                user_model: User model.
        """
        if isinstance(user_model, SessionUserModel):
            self.user_model = user_model
        else:
            self.user_model = SessionUserModel(user_model)

    def get_id(self) -> str:
        """Return the stable user id required by Flask-Login."""
        return str(self.user_model.id)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying session model."""
        return getattr(self.user_model, name)

    def to_dict(self) -> dict[str, Any]:
        """Return the serialized session payload."""
        return self.user_model.to_dict()

    def has_permission(self, permission: str) -> bool:
        """Return whether the session user has the requested permission."""
        if not permission:
            return False
        if self.is_superuser:
            return True
        return (
            permission in self.user_model.permissions
            and permission not in self.user_model.denied_permissions
        )

    def has_min_access_level(self, level: int) -> bool:
        """Return whether the session user meets a minimum access level."""
        return int(self.user_model.access_level) >= int(level)

    @property
    def access_level(self) -> int:
        """Expose access level for route decorators and templates."""
        return int(self.user_model.access_level)

    @property
    def is_superuser(self) -> bool:
        """Return whether the session user is a superuser."""
        return "superuser" in set(self.user_model.roles)
