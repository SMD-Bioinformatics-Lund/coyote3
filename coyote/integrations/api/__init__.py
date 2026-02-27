"""Flask-to-API transport helpers for web routes."""

from coyote.integrations.api.api_client import (
    ApiRequestError,
    CoyoteApiClient,
    build_forward_headers,
    build_internal_headers,
    forward_headers,
    get_web_api_client,
)
from coyote.integrations.api.base import ApiPayload
from coyote.integrations.api.web import log_api_error
from . import endpoints

__all__ = [
    "ApiPayload",
    "ApiRequestError",
    "CoyoteApiClient",
    "build_forward_headers",
    "build_internal_headers",
    "endpoints",
    "forward_headers",
    "get_web_api_client",
    "log_api_error",
]
