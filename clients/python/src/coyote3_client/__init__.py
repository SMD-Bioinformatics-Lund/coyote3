"""API client helpers for external automation and scripts."""

from coyote3_client.async_client import AsyncCoyoteClient
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
    "CoyoteClient",
    "AsyncCoyoteClient",
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
