"""Framework-neutral bootstrap context for API runtime dependencies."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pymongo.errors import ConnectionFailure

import config
from api.extensions import ldap_manager, store, util


@dataclass
class ApiRuntimeContext:
    """Lightweight app-like object for configuration and logging."""

    config: dict[str, Any]
    logger: logging.Logger

    @property
    def secret_key(self) -> str | None:
        return self.config.get("SECRET_KEY")


def create_runtime_context(testing: bool = False, development: bool = False) -> ApiRuntimeContext:
    """
    Build runtime configuration and initialize API dependencies.
    """
    config_obj = _select_config(testing=testing, development=development)
    conf = _config_dict(config_obj)
    logger = logging.getLogger("coyote.api")
    runtime = ApiRuntimeContext(config=conf, logger=logger)

    _init_store(runtime)
    ldap_manager.init_from_config(runtime.config)
    util.init_util()

    return runtime


def _select_config(testing: bool, development: bool):
    if testing:
        return config.TestConfig()
    if development:
        return config.DevelopmentConfig()
    return config.ProductionConfig()


def _config_dict(config_obj) -> dict[str, Any]:
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
