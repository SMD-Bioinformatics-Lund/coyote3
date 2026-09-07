"""Infrastructure-safe request context helpers."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_current_user: ContextVar[Any | None] = ContextVar("api_current_user", default=None)
_current_request_id: ContextVar[str | None] = ContextVar("api_current_request_id", default=None)


def set_current_user(user: Any) -> Token:
    """Bind the current authenticated user to this execution context."""
    return _current_user.set(user)


def reset_current_user(token: Token) -> None:
    """Reset the current authenticated user context."""
    try:
        _current_user.reset(token)
    except ValueError:
        _current_user.set(None)


def current_user() -> Any | None:
    """Return the current authenticated user, when one is bound."""
    return _current_user.get()


def current_username(default: str = "api") -> str:
    """Return the current username with a safe fallback."""
    user = current_user()
    username = getattr(user, "username", None) if user is not None else None
    return str(username) if username else default


def current_user_is_superuser() -> bool:
    """Return whether the current user has unrestricted superuser scope."""
    user = current_user()
    is_superuser = getattr(user, "is_superuser", None) if user is not None else None
    return bool(is_superuser)


def set_current_request_id(request_id: str | None) -> Token:
    """Bind the current request id to this execution context."""
    return _current_request_id.set(request_id)


def reset_current_request_id(token: Token) -> None:
    """Reset the current request id context."""
    try:
        _current_request_id.reset(token)
    except ValueError:
        _current_request_id.set(None)


def current_request_id(default: str = "-") -> str:
    """Return the current request id with a safe fallback."""
    request_id = _current_request_id.get()
    return str(request_id) if request_id else default
