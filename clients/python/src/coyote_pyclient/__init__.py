# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""API client helpers for external automation and scripts."""

from coyote_pyclient.async_client import AsyncCoyoteClient
from coyote_pyclient.errors import (
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
from coyote_pyclient.resources import CoyoteClient

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
