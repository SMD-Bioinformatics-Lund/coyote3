"""API client helpers for external automation and scripts."""

from coyote3_client.async_client import AsyncCoyoteClient
from coyote3_client.auth import ApiLoginSession, login_with_password, login_with_token
from coyote3_client.errors import (
    AuthenticationError,
    ConflictError,
    CoyoteAPIError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestValidationError,
    ResourceNotLoadedError,
    ResponseValidationError,
)
from coyote3_client.resources import CoyoteClient

__all__ = [
    "ApiLoginSession",
    "CoyoteClient",
    "AsyncCoyoteClient",
    "login_with_password",
    "login_with_token",
    "AuthenticationError",
    "ConflictError",
    "CoyoteAPIError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "RequestValidationError",
    "ResourceNotLoadedError",
    "ResponseValidationError",
]
