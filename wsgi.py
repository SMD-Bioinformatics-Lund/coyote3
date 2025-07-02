# -*- coding: utf-8 -*-
"""
WSGI Configuration for Coyote3
==============================

This file serves as the entry point for running the Coyote3 application in
both development and production environments. It includes logging setup
for Gunicorn and standalone modes.

Author: Coyote3 authors
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging.config
import os
from typing import Any

from coyote import init_app
from logging_setup import add_unique_handlers, custom_logging

app = init_app()

if __name__ != "__main__":
    print("Setting up Gunicorn logging.")
    log_dir: str | Any = os.getenv(
        "LOG_DIR", app.config.get("LOGS", "logs/prod")
    )
    custom_logging(
        log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=True
    )

    gunicorn_logger_error = logging.getLogger("gunicorn.error")
    gunicorn_logger_access = logging.getLogger("gunicorn.access")

    # Add unique handlers from gunicorn loggers to app logger
    add_unique_handlers(app.logger, gunicorn_logger_error.handlers)
    add_unique_handlers(app.logger, gunicorn_logger_access.handlers)

    # Set the app logger level to the gunicorn error logger level (you can choose which one to match)
    app.logger.setLevel(gunicorn_logger_error.level)
    app.logger.error("This is an error message")

if __name__ == "__main__":
    log_dir = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(
        log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=False
    )
    app.run(host="0.0.0.0", port=8000, debug=True)
