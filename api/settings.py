"""Centralized API runtime and security setting helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

_PROD_BLOCKED_VALUES: dict[str, set[str]] = {
    "SECRET_KEY": {"ci-test-secret-key", "coyote3-api-dev-only"},
    "INTERNAL_API_TOKEN": {"ci-test-internal-token"},
    "API_SESSION_SALT": {"coyote3-api-session-v1-dev-only"},
}


def _to_bool(value: Any, default: bool = False) -> bool:
    """Handle  to bool.

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
    """Handle  is non production.

    Args:
            config: Config. Optional argument.

    Returns:
            The  is non production result.
    """
    if config is None:
        return to_bool(os.getenv("TESTING"), False) or to_bool(os.getenv("DEVELOPMENT"), False)
    return (
        to_bool(config.get("TESTING"), False)
        or to_bool(config.get("DEVELOPMENT"), False)
        or _is_non_production(None)
    )


def _require_setting(config: Mapping[str, Any], key: str) -> str:
    """Handle  require setting.

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
    """Read environment-backed runtime mode flags.

    Returns:
        A mapping containing the normalized ``testing`` and ``development``
        runtime flags.
    """
    return {
        "testing": to_bool(os.getenv("TESTING"), default=False),
        "development": to_bool(os.getenv("DEVELOPMENT"), default=False),
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
