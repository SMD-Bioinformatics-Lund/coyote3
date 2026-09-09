"""Runtime state and request-context helpers for the API."""

from __future__ import annotations

import logging
from contextvars import Token
from dataclasses import dataclass
from typing import Any

from api.infra import request_context


@dataclass
class _RuntimeApp:
    """Hold process-wide configuration, logger, and an optional initialized cache.

    Attributes:
        config: Runtime settings, initially an empty dictionary.
        logger: Logger used before and after runtime bootstrap.
        cache: Bound cache backend, or None before cache initialization.
    """

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None


app = _RuntimeApp(config={}, logger=logging.getLogger("api.app.runtime_state"))


def bind_runtime_context(runtime_context) -> None:
    """Replace process-wide runtime settings and shared service references.

    Args:
        runtime_context: Object supplying config and logger, plus optional cache.
            Configuration is shallow-copied; logger/cache remain shared. Missing
            cache resets the bound cache to None.
    """
    app.config = dict(runtime_context.config)
    app.logger = runtime_context.logger
    app.cache = getattr(runtime_context, "cache", None)


def set_current_user(user: Any) -> Token:
    """Bind the user to the current execution context.

    Args:
        user: API user object, or None to clear the current identity.

    Returns:
        Context token for restoring the previous binding with reset_current_user.
    """
    return request_context.set_current_user(user)


def reset_current_user(token: Token) -> None:
    """Restore a previous user binding, clearing it on a context mismatch.

    Args:
        token: Token from set_current_user. A mismatched-context ValueError is
            handled by binding None instead.

    Raises:
        RuntimeError: The token has already been used for a reset.
    """
    request_context.reset_current_user(token)


def current_user() -> Any | None:
    """Get request-local API user context."""
    return request_context.current_user()


def current_username(default: str = "api") -> str:
    """Resolve the bound user's username as text, with a fallback.

    Args:
        default: Value returned when the user or its username is absent/falsy;
            defaults to "api".

    Returns:
        str(username) for a truthy username, otherwise default unchanged.
    """
    return request_context.current_username(default=default)


def current_user_is_superuser() -> bool:
    """Resolve current request unrestricted superuser flag."""
    return request_context.current_user_is_superuser()


def set_current_request_id(request_id: str | None) -> Token:
    """Bind a request correlation ID to the current execution context.

    Args:
        request_id: Correlation ID, or None to clear the binding.

    Returns:
        Context token for restoring the prior request ID.
    """
    return request_context.set_current_request_id(request_id)


def reset_current_request_id(token: Token) -> None:
    """Restore a previous request ID, clearing it on a context mismatch.

    Args:
        token: Token from set_current_request_id. A mismatched-context ValueError
            is handled by binding None instead.

    Raises:
        RuntimeError: The token has already been used for a reset.
    """
    request_context.reset_current_request_id(token)


def current_request_id(default: str = "-") -> str:
    """Resolve the bound request ID as text, with a fallback.

    Args:
        default: Value for an absent or falsy request ID; defaults to "-".

    Returns:
        The truthy request ID as text, otherwise default unchanged.
    """
    return request_context.current_request_id(default=default)
