"""Centralized API runtime and security setting helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from api.config.constants import DEFAULT_ENVIRONMENT

_PROD_BLOCKED_VALUES: dict[str, set[str]] = {
    "SECRET_KEY": {"ci-test-secret-key", "coyote3-api-dev-only"},
    "INTERNAL_API_TOKEN": {"ci-test-internal-token"},
    "API_SESSION_SALT": {"coyote3-api-session-v1-dev-only"},
}


def _to_bool(value: Any, default: bool = False) -> bool:
    """To bool.

    Args:
            value: Value.
            default: Default. Optional argument.

    Returns:
            The  to bool result.
    """
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def to_bool(value: Any, default: bool = False) -> bool:
    """Convert a configuration value into a boolean.

    Args:
        value: Raw configuration value from environment or runtime config.
        default: Fallback value when ``value`` is ``None``.

    Returns:
        The normalized boolean interpretation of ``value``.
    """
    return _to_bool(value, default=default)


def _is_non_production(config: Mapping[str, Any] | None = None) -> bool:
    """Is non production.

    Args:
            config: Config. Optional argument.

    Returns:
            The  is non production result.
    """
    if config is None:
        env_name = str(os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT).strip().lower()
    else:
        env_name = (
            str(config.get("ENV_NAME") or os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT)
            .strip()
            .lower()
        )
    return env_name in {"dev", "development", "test", "testing", "stage", "staging"}


def _require_setting(config: Mapping[str, Any], key: str) -> str:
    """Require setting.

    Args:
            config: Config.
            key: Key.

    Returns:
            The  require setting result.
    """
    value = str(config.get(key) or "").strip()
    if value:
        return value
    raise RuntimeError(f"Missing required API setting: {key}")


def _require_production_safe_setting(config: Mapping[str, Any], key: str) -> str:
    """Return required setting and block known test/dev placeholder values in production."""
    value = _require_setting(config, key)
    if value in _PROD_BLOCKED_VALUES.get(key, set()):
        raise RuntimeError(
            f"Insecure production setting for {key}: test/development placeholder values are not allowed."
        )
    return value


def configure_process_env() -> None:
    """Ensure API runtime process defaults are always set.

    Returns:
        ``None``. Process environment values are updated as a side effect.
    """
    return None


def get_runtime_mode_flags() -> dict[str, bool]:
    """Read runtime mode flags from ``ENV_NAME``.

    Returns:
        A mapping containing the normalized ``testing`` and ``development``
        runtime flags.
    """
    env_name = str(os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT).strip().lower()
    return {
        "testing": env_name in {"test", "testing"},
        "development": env_name in {"dev", "development"},
    }


def get_api_secret_key(config: Mapping[str, Any]) -> str:
    """Return the API secret key for the active runtime mode.

    Args:
        config: Runtime configuration mapping.

    Returns:
        The API secret key.
    """
    if _is_non_production(config):
        return str(config.get("SECRET_KEY") or "coyote3-api-dev-only")
    return _require_production_safe_setting(config, "SECRET_KEY")


def get_internal_api_token(config: Mapping[str, Any]) -> str:
    """Return the internal API token for trusted service-to-service calls.

    Args:
        config: Runtime configuration mapping.

    Returns:
        The internal API token.
    """
    if _is_non_production(config):
        return str(config.get("INTERNAL_API_TOKEN") or config.get("SECRET_KEY") or "")
    return _require_production_safe_setting(config, "INTERNAL_API_TOKEN")


def get_api_session_salt(config: Mapping[str, Any]) -> str:
    """Return the salt used to sign API session tokens.

    Args:
        config: Runtime configuration mapping.

    Returns:
        The session-signing salt.
    """
    if _is_non_production(config):
        return str(config.get("API_SESSION_SALT", "coyote3-api-session-v1-dev-only"))
    return _require_production_safe_setting(config, "API_SESSION_SALT")


def get_api_session_cookie_name(config: Mapping[str, Any]) -> str:
    """Return the configured API session cookie name.

    Args:
        config: Runtime configuration mapping.

    Returns:
        The cookie name used for API sessions.
    """
    return str(config.get("API_SESSION_COOKIE_NAME") or "coyote3_api_session")


def get_api_session_ttl_seconds(config: Mapping[str, Any]) -> int:
    """Return the API session lifetime in seconds.

    Args:
        config: Runtime configuration mapping.

    Returns:
        Session lifetime in seconds.
    """
    value = config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 12 * 60 * 60


def get_api_session_cookie_secure(config: Mapping[str, Any]) -> bool:
    """Return whether the API session cookie must be marked secure.

    Args:
        config: Runtime configuration mapping.

    Returns:
        ``True`` when the session cookie should only be sent over HTTPS.
    """
    return to_bool(config.get("SESSION_COOKIE_SECURE"), default=not _is_non_production(config))


def get_api_session_cookie_samesite(config: Mapping[str, Any]) -> str:
    """Return the session cookie SameSite policy."""
    value = str(config.get("API_SESSION_COOKIE_SAMESITE") or "lax").strip().lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def get_api_sessions_collection_name(config: Mapping[str, Any]) -> str:
    """Return the MongoDB collection used for API sessions."""
    return "api_sessions"


def get_audit_events_collection_name(config: Mapping[str, Any]) -> str:
    """Return the MongoDB collection used for durable audit events."""
    return "audit_events"


def get_audit_retention_days(config: Mapping[str, Any]) -> int:
    """Return audit retention in days."""
    try:
        return int(config.get("AUDIT_RETENTION_DAYS", 730))
    except (TypeError, ValueError):
        return 730


def get_runtime_environment(config: Mapping[str, Any]) -> str:
    """Return the normalized runtime environment label."""
    env_name = str(config.get("ENV_NAME") or "production").strip().lower()
    if env_name in {"dev", "development"}:
        return "development"
    if env_name in {"test", "testing"}:
        return "test"
    if env_name in {"stage", "staging"}:
        return "staging"
    return env_name or "production"
