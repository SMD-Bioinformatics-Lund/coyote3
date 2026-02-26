"""WSGI entrypoint for the Coyote3 Flask web app."""

import logging
import os
from typing import Any

from coyote import init_app
from logging_setup import add_unique_handlers, custom_logging


app = init_app(
    testing=bool(int(os.getenv("TESTING", "0"))),
    development=bool(int(os.getenv("DEVELOPMENT", "0"))),
)
app.secret_key = app.config.get("SECRET_KEY")


if __name__ != "__main__":
    log_dir: str | Any = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True), gunicorn_logging=True)

    gunicorn_logger_error = logging.getLogger("gunicorn.error")
    gunicorn_logger_access = logging.getLogger("gunicorn.access")

    add_unique_handlers(app.logger, gunicorn_logger_error.handlers)
    add_unique_handlers(app.logger, gunicorn_logger_access.handlers)
    app.logger.setLevel(gunicorn_logger_error.level)


if __name__ == "__main__":
    log_dir = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", True))
    app.run(host="0.0.0.0", port=8000, debug=bool(int(os.getenv("FLASK_DEBUG", "0"))))
