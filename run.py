"""Flask UI launcher with explicit runtime mode handling.

This launcher starts only the web presentation runtime and mirrors the
environment-sensitive setup used by containerized deployments:
- production -> ProductionConfig, logs/prod, debug off
- development -> DevelopmentConfig, logs/dev, debug on by default
- testing -> TestConfig, logs/test, debug on by default
"""

from __future__ import annotations

import os
from typing import Literal

from coyote import init_app
from logging_setup import custom_logging

RunMode = Literal["production", "development", "testing"]
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in _TRUE_VALUES


def _resolve_mode() -> RunMode:
    requested = str(os.getenv("COYOTE3_RUN_MODE", "")).strip().lower()
    aliases = {
        "prod": "production",
        "production": "production",
        "dev": "development",
        "development": "development",
        "test": "testing",
        "testing": "testing",
    }
    if requested in aliases:
        return aliases[requested]
    if _env_bool("TESTING"):
        return "testing"
    if _env_bool("DEVELOPMENT"):
        return "development"
    return "production"


def _apply_mode_defaults(mode: RunMode) -> tuple[bool, bool]:
    if mode == "testing":
        os.environ["TESTING"] = "1"
        os.environ["DEVELOPMENT"] = "0"
        os.environ.setdefault("FLASK_DEBUG", "1")
        return True, False
    if mode == "development":
        os.environ["TESTING"] = "0"
        os.environ["DEVELOPMENT"] = "1"
        os.environ.setdefault("FLASK_DEBUG", "1")
        return False, True
    os.environ["TESTING"] = "0"
    os.environ["DEVELOPMENT"] = "0"
    os.environ.setdefault("FLASK_DEBUG", "0")
    return False, False


_mode = _resolve_mode()
_testing, _development = _apply_mode_defaults(_mode)

app = init_app(testing=_testing, development=_development)
app.secret_key = app.config.get("SECRET_KEY")


if __name__ == "__main__":
    log_dir = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True))
    host = os.getenv("HOST", os.getenv("FLASK_RUN_HOST", "0.0.0.0"))
    port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", "8000")))
    app.run(host=host, port=port, debug=_env_bool("FLASK_DEBUG"))
