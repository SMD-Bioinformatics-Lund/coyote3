"""Framework-neutral setup for API runtime dependencies."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout

from api.app.container import ldap_manager, store, util
from api.config import app_config
from api.config.constants import AUTH_PROVIDER_LDAP, AUTH_TYPE_OPTIONS
from api.config.mongo import mongo_endpoints
from api.infra.cache import create_cache_backend
from api.infra.observability.logging import configure_json_logging
from api.infra.observability.prometheus_metrics import set_startup_phase_duration


@dataclass
class ApiRuntimeContext:
    """Lightweight app-like object for configuration and logging."""

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None

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
        Dependency setup errors propagate; partial initialization is not rolled back.
    """
    startup_started = time.perf_counter()
    config_obj = _select_config(testing=testing, development=development)
    conf = _config_dict(config_obj)
    mongo_endpoints(conf)
    configure_json_logging(
        service_name=str(conf.get("LOG_SERVICE_NAME") or "api"),
        level=str(conf.get("LOG_LEVEL") or "INFO"),
        log_root=str(conf.get("LOG_ROOT", "logs")),
        file_enabled=bool(conf.get("LOG_FILE_ENABLED", True)),
        retention_days=int(conf.get("LOG_RETENTION_DAYS", 30)),
        timezone_name=str(conf.get("LOG_TIMEZONE") or "UTC"),
    )
    logger = logging.getLogger("coyote.api")
    logger.info(
        "Runtime banner: env=%s version=%s git=%s build=%s",
        conf.get("ENV_NAME"),
        conf.get("APP_VERSION"),
        conf.get("GIT_COMMIT", "unknown"),
        conf.get("BUILD_TIME", "unknown"),
    )
    runtime = ApiRuntimeContext(config=conf, logger=logger)

    phase_started = time.perf_counter()
    _init_cache(runtime)
    set_startup_phase_duration(
        phase="cache", duration_ms=(time.perf_counter() - phase_started) * 1000.0
    )
    phase_started = time.perf_counter()
    _init_store(runtime)
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
    util.init_util()
    total_ms = (time.perf_counter() - startup_started) * 1000.0
    set_startup_phase_duration(phase="total", duration_ms=total_ms)
    logger.info("runtime_initialized duration_ms=%.2f", total_ms)

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
        return app_config.TestConfig()
    if development:
        return app_config.DevelopmentConfig()
    env_name = os.getenv("ENV_NAME", "").strip().lower()
    if env_name in {"stage", "staging"}:
        app_config.StageConfig.validate_required_env()
        return app_config.StageConfig()
    app_config.ProductionConfig.validate_required_env()
    return app_config.ProductionConfig()


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
            store.reset()
            store.init_from_app(runtime)
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
