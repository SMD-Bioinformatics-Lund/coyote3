"""Web session user model for Flask-Login.

This module is web-owned and intentionally avoids importing API internals.
It stores only the fields needed by Flask routes and templates.
"""

from __future__ import annotations

from typing import Any

from flask_login import UserMixin


class SessionUserModel:
    """Minimal session user payload used by the web app.

    Args:
        payload: User dictionary returned by API auth endpoints.
    """

    def __init__(self, payload: dict[str, Any]):
        """Handle __init__.

        Args:
                payload: Payload.
        """
        self.id = str(payload.get("_id") or payload.get("id") or "")
        self.email = str(payload.get("email") or "")
        self.fullname = str(payload.get("fullname") or "")
        self.username = str(payload.get("username") or "")
        self.role = str(payload.get("role") or "")
        self.access_level = int(payload.get("access_level") or 0)
        self.permissions = list(payload.get("permissions") or [])
        self.denied_permissions = list(payload.get("denied_permissions") or [])
        self.assays = list(payload.get("assays") or [])
        self.assay_groups = list(payload.get("assay_groups") or [])
        self.envs = list(payload.get("envs") or [])
        self.asp_map = dict(payload.get("asp_map") or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize user fields into a JSON-safe dict for session storage."""
        return {
            "_id": self.id,
            "email": self.email,
            "fullname": self.fullname,
            "username": self.username,
            "role": self.role,
            "access_level": self.access_level,
            "permissions": list(self.permissions),
            "denied_permissions": list(self.denied_permissions),
            "assays": list(self.assays),
            "assay_groups": list(self.assay_groups),
            "envs": list(self.envs),
            "asp_map": dict(self.asp_map),
        }


class User(UserMixin):
    """Flask-Login user wrapper backed by :class:`SessionUserModel`."""

    def __init__(self, user_model: SessionUserModel | dict[str, Any]):
        """Handle __init__.

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

    @property
    def access_level(self) -> int:
        """Expose access level for route decorators and templates."""
        return int(self.user_model.access_level)
