"""Application entry point."""

import logging.config
from logging import Logger
from typing import Dict, Any

from flask import Flask
import gunicorn.glogging
from coyote import init_app
from logging_setup import custom_logging, add_unique_handlers
import os

app = init_app()

if __name__ != "__main__":
    print("Setting up Gunicorn logging.")
    log_dir: str | Any = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=True)

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
    custom_logging(log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=False)
    app.run(host="0.0.0.0")
