# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Framework-neutral setup for API runtime dependencies."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from coyote.config.constants import AUTH_PROVIDER_LDAP, AUTH_TYPE_OPTIONS
from coyote.config.factory_defaults import factory_value
from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout

from coyote_api.app.container import MongoStore, ldap_manager, store
from coyote_api.config import runtime_settings
from coyote_api.config.backend import BackendSettings
from coyote_api.config.factory_defaults import api_default
from coyote_api.infra.cache import create_cache_backend
from coyote_api.infra.observability.logging import configure_json_logging
from coyote_api.infra.observability.prometheus_metrics import set_startup_phase_duration


@dataclass
class ApiRuntimeContext:
    """Lightweight app-like object for configuration and logging."""

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None
    store: MongoStore = field(default_factory=lambda: store)
    _adapter: Any | None = field(default=None, init=False, repr=False)

    def close(self) -> None:
        """Release only this context's connections, including partial startup."""
        cache, self.cache = self.cache, None
        adapter, self._adapter = self._adapter, None
        try:
            if adapter is not None and self.store._adapter is adapter:
                try:
                    self.store.reset()
                finally:
                    ldap_manager.reset()
        finally:
            if cache is not None:
                cache.close()

    @cached_property
    def backend_settings(self) -> BackendSettings:
        """Validate and retain package-specific settings once for this backend runtime."""
        return BackendSettings.from_runtime(self.config)

    @property
    def secret_key(self) -> str | None:
        """Return the configured secret key when available."""
        return self.config.get("SECRET_KEY")


def create_runtime_context(testing: bool = False, development: bool = False) -> ApiRuntimeContext:
    """Build runtime configuration and initialize shared API dependencies.

    Args:
        testing: Use test configuration when True; defaults to False and takes
            precedence over development.
        development: Use development configuration when True and not testing;
            otherwise ENV_NAME selects staging or production. Defaults to False.

    Returns:
        A context containing settings, the configured API logger, and cache backend.

    Raises:
        RuntimeError: Required environment or MongoDB configuration is invalid,
            or the store's initial database ping fails.

    Notes:
        Configures process logging, initializes cache and MongoDB, optionally
        initializes LDAP, and initializes shared utilities. Records startup timings.
        Dependency setup errors propagate after releasing resources already acquired.
    """
    startup_started = time.perf_counter()
    config_obj = _select_config(testing=testing, development=development)
    conf = _config_dict(config_obj)
    # Validate package inputs before initializing logging, caches or connections.
    runtime = ApiRuntimeContext(config=conf, logger=logging.getLogger("coyote.api"))
    _ = runtime.backend_settings
    configure_json_logging(
        service_name=str(
            conf.get("LOG_SERVICE_NAME") or api_default("runtime.LOG_SERVICE_NAME", str)
        ),
        level=str(conf.get("LOG_LEVEL") or api_default("runtime.LOG_LEVEL", str)),
        log_root=str(conf.get("LOG_ROOT", api_default("runtime.LOG_ROOT", str))),
        file_enabled=bool(
            conf.get("LOG_FILE_ENABLED", api_default("runtime.LOG_FILE_ENABLED", bool))
        ),
        retention_days=int(
            conf.get(
                "LOG_RETENTION_DAYS",
                int(factory_value("controls.RetentionControlDoc.disk_log_days")),
            )
        ),
        timezone_name=str(conf.get("LOG_TIMEZONE") or api_default("runtime.LOCAL_TIME_ZONE", str)),
    )
    logger = logging.getLogger("coyote.api")
    logger.info(
        "Runtime banner: env=%s version=%s git=%s build=%s",
        conf.get("ENV_NAME"),
        conf.get("APP_VERSION"),
        conf.get("GIT_COMMIT", "unknown"),
        conf.get("BUILD_TIME", "unknown"),
    )

    try:
        phase_started = time.perf_counter()
        _init_cache(runtime)
        set_startup_phase_duration(
            phase="cache", duration_ms=(time.perf_counter() - phase_started) * 1000.0
        )
        phase_started = time.perf_counter()
        _init_store(runtime)
        runtime._adapter = runtime.store._adapter
        set_startup_phase_duration(
            phase="database_and_indexes",
            duration_ms=(time.perf_counter() - phase_started) * 1000.0,
        )
        if AUTH_PROVIDER_LDAP in AUTH_TYPE_OPTIONS:
            phase_started = time.perf_counter()
            ldap_manager.init_from_config(runtime.config)
            set_startup_phase_duration(
                phase="ldap", duration_ms=(time.perf_counter() - phase_started) * 1000.0
            )
        total_ms = (time.perf_counter() - startup_started) * 1000.0
        set_startup_phase_duration(phase="total", duration_ms=total_ms)
        logger.info("runtime_initialized duration_ms=%.2f", total_ms)
    except BaseException:
        try:
            runtime.close()
        except Exception:
            logger.exception("Runtime cleanup failed after startup error")
        raise

    return runtime


def _select_config(testing: bool, development: bool):
    """Select the active configuration object.

    Args:
        testing: Whether the process is running in test mode.
        development: Whether the process is running in development mode.

    Returns:
        object: Concrete configuration instance for the current runtime.
    """
    if testing:
        return runtime_settings.TestConfig()
    if development:
        return runtime_settings.DevelopmentConfig()
    env_name = os.getenv("ENV_NAME", "").strip().lower()
    if env_name in {"stage", "staging"}:
        runtime_settings.StageConfig.validate_required_env()
        return runtime_settings.StageConfig()
    runtime_settings.ProductionConfig.validate_required_env()
    return runtime_settings.ProductionConfig()


def _config_dict(config_obj) -> dict[str, Any]:
    """Extract uppercase settings from a config object.

    Args:
        config_obj: Configuration instance to serialize.

    Returns:
        dict[str, Any]: Uppercase settings ready for runtime use.
    """
    out: dict[str, Any] = {}
    for name in dir(config_obj):
        if not name.isupper():
            continue
        out[name] = getattr(config_obj, name)
    out.setdefault("SECRET_KEY_FALLBACKS", [])
    return out


def _init_store(runtime: ApiRuntimeContext) -> None:
    """Reset and initialize the store, retrying selected MongoDB connection errors.

    Args:
        runtime: Configuration and logger supplied to the shared store.

    Raises:
        AutoReconnect: Reconnection still fails on the fifth attempt.
        ConnectionFailure: An unwrapped connection failure persists for five attempts.
        NetworkTimeout: Network timeouts persist for five attempts.
        RuntimeError: Store initialization wraps a failed ping; this is not retried.

    Notes:
        Resets the store on each attempt and sleeps two seconds between retries.
        Errors outside the three retried PyMongo types propagate immediately.
    """
    max_retries = 5
    retry_delay = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            runtime.store.reset()
            runtime.store.init_from_app(runtime)
            return
        except (AutoReconnect, ConnectionFailure, NetworkTimeout) as exc:
            if attempt < max_retries:
                runtime.logger.warning(
                    "MongoDB connection failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                runtime.logger.error(
                    "MongoDB connection failed after %d attempts: %s", max_retries, exc
                )
                raise


def _init_cache(runtime: ApiRuntimeContext) -> None:
    """Create the API cache backend and bind it to the runtime context.

    Args:
        runtime: Context whose config/logger configure the backend and whose cache
            attribute is replaced. The cache namespace is "api".
    """
    runtime.cache = create_cache_backend(
        config=runtime.config,
        logger=runtime.logger,
        namespace="api",
    )
