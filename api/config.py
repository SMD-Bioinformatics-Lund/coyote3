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
    "get_enabled_knowledgebase_plugins",
]


def get_mongo_settings(config: Mapping[str, Any]) -> dict[str, str]:
    """Extract the Mongo settings needed by the API runtime."""
    return {
        "uri": str(config.get("MONGO_URI") or ""),
        "db_name": str(config.get("COYOTE3_DB") or ""),
        "bam_db_name": str(config.get("BAM_DB") or ""),
    }


def get_enabled_knowledgebase_plugins(config: Mapping[str, Any]) -> list[str]:
    """Return enabled knowledgebase plugin names for the Mongo runtime."""
    raw_value = config.get("KNOWLEDGEBASE_PLUGINS")
    if raw_value is None:
        return ["all"]
    if isinstance(raw_value, str):
        normalized = [part.strip().lower() for part in raw_value.split(",") if part.strip()]
        return normalized or ["all"]
    if isinstance(raw_value, (list, tuple, set)):
        normalized = [str(value).strip().lower() for value in raw_value if str(value).strip()]
        return normalized or ["all"]
    text = str(raw_value).strip().lower()
    return [text] if text else ["all"]
