# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Request metadata shared with audit and logging without a web-framework dependency."""

from contextvars import ContextVar, Token

from pydantic import BaseModel, ConfigDict


class RequestContext(BaseModel):
    """Immutable request identity and bounded transport metadata supplied by a host."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    client_ip: str | None
    method: str
    path: str
    user_agent: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "coyote_request_context", default=None
)


def current_request_context() -> RequestContext | None:
    """Return request metadata for this execution, or None outside a request."""
    return _request_context.get()


def bind_request_context(context: RequestContext) -> Token:
    """Bind request metadata for subsequent logging and transactional audit events.

    Args:
        context: Validated metadata supplied by the host for this execution.

    Returns:
        Token used to restore the previous context after the request finishes.
    """
    return _request_context.set(context)


def reset_request_context(token: Token) -> None:
    """Restore the previous request context.

    Args:
        token: Token returned by bind_request_context in this execution context.

    Raises:
        ValueError: The token belongs to another context or variable.
        RuntimeError: The token has already been used.
    """
    _request_context.reset(token)
