"""Centralized API runtime and security setting helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def to_bool(value: Any, default: bool = False) -> bool:
    return _to_bool(value, default=default)


def configure_process_env() -> None:
    """Ensure API runtime process defaults are always set."""
    os.environ["REQUIRE_EXTERNAL_API"] = "0"


def get_runtime_mode_flags() -> dict[str, bool]:
    """Read environment-backed runtime mode flags."""
    return {
        "testing": to_bool(os.getenv("TESTING"), default=False),
        "development": to_bool(os.getenv("DEVELOPMENT"), default=False),
    }


def get_api_secret_key(config: Mapping[str, Any]) -> str:
    return str(config.get("SECRET_KEY") or "coyote3-api")


def get_internal_api_token(config: Mapping[str, Any]) -> str:
    return str(config.get("INTERNAL_API_TOKEN") or config.get("SECRET_KEY") or "")


def get_api_session_salt(config: Mapping[str, Any]) -> str:
    return str(config.get("API_SESSION_SALT", "coyote3-api-session-v1"))


def get_api_session_cookie_name(config: Mapping[str, Any]) -> str:
    return str(config.get("API_SESSION_COOKIE_NAME") or "coyote3_api_session")


def get_api_session_ttl_seconds(config: Mapping[str, Any]) -> int:
    value = config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 12 * 60 * 60


def get_api_session_cookie_secure(config: Mapping[str, Any]) -> bool:
    return to_bool(config.get("SESSION_COOKIE_SECURE"), default=False)
