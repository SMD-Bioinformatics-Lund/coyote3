import logging_setup
import os

log_dir = os.getenv("LOG_DIR", "logs/prod")


def when_ready(server):
    logging_setup.setup_gunicorn_logging(log_dir, is_production=True)
