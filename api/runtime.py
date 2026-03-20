"""Runtime context helpers for API-owned services."""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass
class _RuntimeApp:
    """Provide  RuntimeApp behavior."""

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None


app = _RuntimeApp(config={}, logger=logging.getLogger("api.runtime"))
_runtime_user: ContextVar[Any | None] = ContextVar("api_runtime_user", default=None)
_runtime_request_id: ContextVar[str | None] = ContextVar("api_runtime_request_id", default=None)


def bind_runtime_context(runtime_context) -> None:
    """Bind runtime config/logger from API bootstrap context."""
    app.config = dict(runtime_context.config)
    app.logger = runtime_context.logger
    app.cache = getattr(runtime_context, "cache", None)


def flash(message: str, category: str = "info") -> None:
    """No-op flash replacement for API runtime."""
    app.logger.debug("flash[%s]: %s", category, message)


def set_current_user(user: Any) -> Token:
    """Set request-local API user context."""
    return _runtime_user.set(user)


def reset_current_user(token: Token) -> None:
    """Reset request-local API user context."""
    try:
        _runtime_user.reset(token)
    except ValueError:
        # FastAPI may finalize sync-generator dependencies in a different context.
        _runtime_user.set(None)


def current_user() -> Any | None:
    """Get request-local API user context."""
    return _runtime_user.get()


def current_username(default: str = "api") -> str:
    """Resolve current request username, with safe fallback."""
    user = current_user()
    username = getattr(user, "username", None) if user is not None else None
    return str(username) if username else default


def current_user_is_admin() -> bool:
    """Resolve current request admin flag."""
    user = current_user()
    role = getattr(user, "role", None) if user is not None else None
    if role is not None:
        return str(role) == "admin"
    is_admin = getattr(user, "is_admin", None) if user is not None else None
    return bool(is_admin)


def set_current_request_id(request_id: str | None) -> Token:
    """Set request-local request-id context."""
    return _runtime_request_id.set(request_id)


def reset_current_request_id(token: Token) -> None:
    """Reset request-local request-id context."""
    try:
        _runtime_request_id.reset(token)
    except ValueError:
        _runtime_request_id.set(None)


def current_request_id(default: str = "-") -> str:
    """Resolve current request-id with fallback."""
    rid = _runtime_request_id.get()
    return str(rid) if rid else default
