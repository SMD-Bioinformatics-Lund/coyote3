#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#


"""
Run Configuration for Coyote3
=============================

This file contains the entry point and configuration for running the Coyote3
application, including logging setup for both Gunicorn and standalone modes.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging.config
from typing import Any
from flask import Flask
from coyote import init_app
from logging_setup import custom_logging, add_unique_handlers
import os


# Command to run this
# gunicorn -w 2 -b 10.231.229.20:8000 run:app


if __name__ != "__main__":
    print("Setting up Gunicorn logging.")
    app: Flask = init_app()
    log_dir: str | Any = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=True)
    app.secret_key = "SomethingSecret"

    gunicorn_logger_error = logging.getLogger("gunicorn.error")
    gunicorn_logger_access = logging.getLogger("gunicorn.access")

    # Add unique handlers from gunicorn loggers to app logger
    add_unique_handlers(app.logger, gunicorn_logger_error.handlers)
    add_unique_handlers(app.logger, gunicorn_logger_access.handlers)

    # Set the app logger level to the gunicorn error logger level (you can choose which one to match)
    app.logger.setLevel(gunicorn_logger_error.level)
    app.logger.error("This is an error message")

if __name__ == "__main__":
    app = init_app(testing=False, debug=True)
    log_dir = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=False)
    app.secret_key = "SomethingSecret"
    app.run(host="0.0.0.0")
