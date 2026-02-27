"""Minimal Flask context bootstrap for API runtime dependencies."""

from __future__ import annotations

from flask import Flask
from pymongo.errors import ConnectionFailure

import config
from api.extensions import ldap_manager, store, util


def create_flask_context_app(testing: bool = False, development: bool = False) -> Flask:
    """
    Create a minimal Flask app used only for API runtime context.

    The API still reuses a few Flask-context dependent helpers. This app intentionally
    avoids registering web blueprints or web-only middleware.
    """
    app = Flask(__name__, instance_relative_config=True)

    if testing:
        app.config.from_object(config.TestConfig())
        app.debug = True
    elif development:
        app.config.from_object(config.DevelopmentConfig())
        app.debug = True
    else:
        app.config.from_object(config.ProductionConfig())

    with app.app_context():
        _init_store(app)
        ldap_manager.init_app(app)
        util.init_util()

    return app


def _init_store(app: Flask) -> None:
    """Initialize API Mongo adapter and verify connectivity."""
    app.logger.info("Initializing API MongoAdapter at: %s", app.config.get("MONGO_URI"))
    store.init_from_app(app)
    try:
        store.client.admin.command("ping")
    except ConnectionFailure as exc:
        app.logger.error("API MongoDB connection failed: %s", exc)
        raise RuntimeError("Could not connect to MongoDB for API runtime.") from exc

