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


def _is_non_production(config: Mapping[str, Any] | None = None) -> bool:
    if config is None:
        return to_bool(os.getenv("TESTING"), False) or to_bool(os.getenv("DEVELOPMENT"), False)
    return (
        to_bool(config.get("TESTING"), False)
        or to_bool(config.get("DEVELOPMENT"), False)
        or _is_non_production(None)
    )


def _require_setting(config: Mapping[str, Any], key: str) -> str:
    value = str(config.get(key) or "").strip()
    if value:
        return value
    raise RuntimeError(f"Missing required API setting: {key}")


def configure_process_env() -> None:
    """Ensure API runtime process defaults are always set."""
    os.environ.setdefault("REQUIRE_EXTERNAL_API", "0" if _is_non_production() else "1")


def get_runtime_mode_flags() -> dict[str, bool]:
    """Read environment-backed runtime mode flags."""
    return {
        "testing": to_bool(os.getenv("TESTING"), default=False),
        "development": to_bool(os.getenv("DEVELOPMENT"), default=False),
    }


def get_api_secret_key(config: Mapping[str, Any]) -> str:
    if _is_non_production(config):
        return str(config.get("SECRET_KEY") or "coyote3-api-dev-only")
    return _require_setting(config, "SECRET_KEY")


def get_internal_api_token(config: Mapping[str, Any]) -> str:
    if _is_non_production(config):
        return str(config.get("INTERNAL_API_TOKEN") or config.get("SECRET_KEY") or "")
    return _require_setting(config, "INTERNAL_API_TOKEN")


def get_api_session_salt(config: Mapping[str, Any]) -> str:
    if _is_non_production(config):
        return str(config.get("API_SESSION_SALT", "coyote3-api-session-v1-dev-only"))
    return _require_setting(config, "API_SESSION_SALT")


def get_api_session_cookie_name(config: Mapping[str, Any]) -> str:
    return str(config.get("API_SESSION_COOKIE_NAME") or "coyote3_api_session")


def get_api_session_ttl_seconds(config: Mapping[str, Any]) -> int:
    value = config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 12 * 60 * 60


def get_api_session_cookie_secure(config: Mapping[str, Any]) -> bool:
    return to_bool(config.get("SESSION_COOKIE_SECURE"), default=not _is_non_production(config))
