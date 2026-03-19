"""Authoritative API configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from api.settings import (
    configure_process_env,
    get_api_secret_key,
    get_api_session_cookie_name,
    get_api_session_cookie_secure,
    get_api_session_salt,
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
    "get_api_session_salt",
    "get_api_session_cookie_name",
    "get_api_session_ttl_seconds",
    "get_api_session_cookie_secure",
    "to_bool",
    "get_mongo_settings",
]


def get_mongo_settings(config: Mapping[str, Any]) -> dict[str, str]:
    """Extract the Mongo settings needed by the API runtime."""
    return {
        "uri": str(config.get("MONGO_URI") or ""),
        "db_name": str(config.get("COYOTE3_DB") or ""),
        "bam_db_name": str(config.get("BAM_DB") or ""),
    }
