"""Authoritative API configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from api.config.mongo import mongo_endpoints
from api.config.security import (
    configure_process_env,
    get_api_secret_key,
    get_api_session_cookie_name,
    get_api_session_cookie_secure,
    get_api_session_ttl_seconds,
    get_internal_api_token,
    get_runtime_mode_flags,
    to_bool,
)

__all__ = [
    "configure_process_env",
    "get_runtime_mode_flags",
    "get_api_secret_key",
    "get_internal_api_token",
    "get_api_session_cookie_name",
    "get_api_session_ttl_seconds",
    "get_api_session_cookie_secure",
    "to_bool",
    "get_mongo_settings",
]


def get_mongo_settings(config: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Extract the Mongo settings needed by the API runtime."""
    return {
        service: {"uri": endpoint.uri, "db_name": endpoint.database}
        for service, endpoint in mongo_endpoints(config).items()
    }
