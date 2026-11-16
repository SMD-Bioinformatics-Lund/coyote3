# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Centralized API runtime and security setting helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from coyote.config.constants import DEFAULT_ENVIRONMENT

from coyote_api.config.factory_defaults import api_default

_PROD_BLOCKED_VALUES: dict[str, set[str]] = {
    "SECRET_KEY": {"ci-test-secret-key", "coyote4-api-dev-only"},
    "INTERNAL_API_TOKEN": {"ci-test-internal-token"},
}


def to_bool(value: Any, default: bool = False) -> bool:
    """Convert a configuration value into a boolean.

    Args:
        value: Raw configuration value from environment or runtime config.
        default: Fallback value when ``value`` is ``None``.

    Returns:
        The normalized boolean interpretation of ``value``.
    """
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_non_production(config: Mapping[str, Any] | None = None) -> bool:
    """Identify development and test environments allowed to use local defaults.

    Args:
        config: Runtime settings; None reads the process environment.

    Returns:
        True for development or testing only. Staging uses production safeguards.
    """
    mode = _explicit_runtime_mode(config)
    if mode is not None:
        return mode in {"development", "testing"}
    if config is None:
        env_name = str(os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT).strip().lower()
    else:
        env_name = (
            str(config.get("ENV_NAME") or os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT)
            .strip()
            .lower()
        )
    return env_name in {"dev", "development", "test", "testing"}


def _explicit_runtime_mode(config: Mapping[str, Any] | None = None) -> str | None:
    """Resolve an explicit security mode independently of the assay environment.

    Args:
        config: Host settings, or None to read the process override. A supplied
            COYOTE4_RUNTIME_MODE takes precedence over the process environment.

    Returns:
        The validated mode, or None when ordinary environment selection applies.

    Raises:
        RuntimeError: An explicit mode is blank or unsupported.
    """
    mode = (
        config["COYOTE4_RUNTIME_MODE"]
        if config is not None and "COYOTE4_RUNTIME_MODE" in config
        else os.getenv("COYOTE4_RUNTIME_MODE")
    )
    if mode is None:
        return None
    mode = str(mode).strip().lower()
    if mode not in {"production", "development", "testing"}:
        raise RuntimeError("COYOTE4_RUNTIME_MODE must be production, development or testing")
    return mode


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


def get_runtime_mode_flags() -> dict[str, bool]:
    """Select process protections independently of the clinical environment label.

    Returns:
        A mapping containing the normalized ``testing`` and ``development``
        runtime flags. COYOTE4_RUNTIME_MODE explicitly selects production,
        development or testing; when absent, ENV_NAME preserves existing behavior.

    Raises:
        RuntimeError: An explicit process mode is unsupported.
    """
    mode = _explicit_runtime_mode()
    env_name = mode or str(os.getenv("ENV_NAME") or DEFAULT_ENVIRONMENT).strip().lower()
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
        return str(config.get("SECRET_KEY") or "coyote4-api-dev-only")
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


def get_api_session_cookie_name(config: Mapping[str, Any]) -> str:
    """Return the configured API session cookie name.

    Args:
        config: Runtime configuration mapping.

    Returns:
        The cookie name used for API sessions.
    """
    return str(
        config.get("API_SESSION_COOKIE_NAME") or api_default("runtime.API_SESSION_COOKIE_NAME", str)
    )


def get_api_session_ttl_seconds(config: Mapping[str, Any]) -> int:
    """Return the API session lifetime in seconds.

    Args:
        config: Runtime configuration mapping.

    Returns:
        Session lifetime in seconds.
    """
    value = config.get(
        "API_SESSION_TTL_SECONDS", api_default("runtime.API_SESSION_TTL_SECONDS", int)
    )
    try:
        return int(value)
    except (TypeError, ValueError):
        return api_default("runtime.API_SESSION_TTL_SECONDS", int)


def get_api_session_cookie_secure(
    config: Mapping[str, Any], *, request_scheme: str | None = None
) -> bool:
    """Return whether the API session cookie must be marked secure.

    Args:
        config: Runtime configuration mapping.
        request_scheme: Effective browser-facing scheme, when available.

    Returns:
        ``True`` for HTTPS. Local HTTP development falls back to a non-secure
        cookie so browser login can proceed.
    """
    scheme = str(request_scheme or "").strip().lower()
    if scheme:
        return scheme == "https"
    return not _is_non_production(config)


def get_api_session_cookie_samesite(config: Mapping[str, Any]) -> str:
    """Return the session cookie SameSite policy."""
    value = (
        str(
            config.get("API_SESSION_COOKIE_SAMESITE")
            or api_default("runtime.API_SESSION_COOKIE_SAMESITE", str)
        )
        .strip()
        .lower()
    )
    return (
        value
        if value in {"lax", "strict", "none"}
        else api_default("runtime.API_SESSION_COOKIE_SAMESITE", str)
    )
