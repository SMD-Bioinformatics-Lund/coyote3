"""Framework-neutral bootstrap context for API runtime dependencies."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from pymongo.errors import ConnectionFailure

import config
from api.extensions import ldap_manager, store, util
from cache_backend import create_cache_backend
from shared.logging import ensure_logging_configured


@dataclass
class ApiRuntimeContext:
    """Lightweight app-like object for configuration and logging."""

    config: dict[str, Any]
    logger: logging.Logger
    cache: Any | None = None

    @property
    def secret_key(self) -> str | None:
        """Secret key.

        Returns:
            str | None: The function result.
        """
        return self.config.get("SECRET_KEY")


def create_runtime_context(testing: bool = False, development: bool = False) -> ApiRuntimeContext:
    """
    Build runtime configuration and initialize API dependencies.
    """
    config_obj = _select_config(testing=testing, development=development)
    conf = _config_dict(config_obj)
    ensure_logging_configured(
        str(conf.get("LOGS", "logs/api")),
        is_production=bool(conf.get("PRODUCTION", False)),
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

    _init_cache(runtime)
    _init_store(runtime)
    ldap_manager.init_from_config(runtime.config)
    util.init_util()

    return runtime


def _select_config(testing: bool, development: bool):
    """Select config.

    Args:
            testing: Testing.
            development: Development.

    Returns:
            The  select config result.
    """
    if testing:
        return config.TestConfig()
    if development:
        return config.DevelopmentConfig()
    env_name = os.getenv("ENV_NAME", "").strip().lower()
    if os.getenv("STAGING", "0") == "1" or env_name == "staging":
        return config.StageConfig()
    return config.ProductionConfig()


def _config_dict(config_obj) -> dict[str, Any]:
    """Config dict.

    Args:
            config_obj: Config obj.

    Returns:
            The  config dict result.
    """
    out: dict[str, Any] = {}
    for name in dir(config_obj):
        if not name.isupper():
            continue
        try:
            out[name] = getattr(config_obj, name)
        except Exception:
            continue
    out.setdefault("SECRET_KEY_FALLBACKS", [])
    return out


def _init_store(runtime: ApiRuntimeContext) -> None:
    """Initialize API Mongo adapter and verify connectivity."""
    runtime.logger.info("Initializing API MongoAdapter at: %s", runtime.config.get("MONGO_URI"))
    store.init_from_app(runtime)
    try:
        store.client.admin.command("ping")
    except ConnectionFailure as exc:
        runtime.logger.error("API MongoDB connection failed: %s", exc)
        raise RuntimeError("Could not connect to MongoDB for API runtime.") from exc


def _init_cache(runtime: ApiRuntimeContext) -> None:
    """Initialize API cache backend."""
    runtime.cache = create_cache_backend(
        config=runtime.config,
        logger=runtime.logger,
        namespace="api",
    )
