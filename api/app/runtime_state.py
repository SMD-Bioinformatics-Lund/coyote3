"""Runtime state and request-context helpers for the API."""

from __future__ import annotations

import logging
from contextvars import Token
from dataclasses import dataclass
from typing import Any

from api.infra import request_context


@dataclass
class _RuntimeApp:
    """Provide  RuntimeApp behavior."""

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None


app = _RuntimeApp(config={}, logger=logging.getLogger("api.app.runtime_state"))


def bind_runtime_context(runtime_context) -> None:
    """Bind runtime config/logger from API bootstrap context."""
    app.config = dict(runtime_context.config)
    app.logger = runtime_context.logger
    app.cache = getattr(runtime_context, "cache", None)


def set_current_user(user: Any) -> Token:
    """Set request-local API user context."""
    return request_context.set_current_user(user)


def reset_current_user(token: Token) -> None:
    """Reset request-local API user context."""
    request_context.reset_current_user(token)


def current_user() -> Any | None:
    """Get request-local API user context."""
    return request_context.current_user()


def current_username(default: str = "api") -> str:
    """Resolve current request username, with safe fallback."""
    return request_context.current_username(default=default)


def current_user_is_superuser() -> bool:
    """Resolve current request unrestricted superuser flag."""
    return request_context.current_user_is_superuser()


def set_current_request_id(request_id: str | None) -> Token:
    """Set request-local request-id context."""
    return request_context.set_current_request_id(request_id)


def reset_current_request_id(token: Token) -> None:
    """Reset request-local request-id context."""
    request_context.reset_current_request_id(token)


def current_request_id(default: str = "-") -> str:
    """Resolve current request-id with fallback."""
    return request_context.current_request_id(default=default)
