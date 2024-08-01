from typing import Any, Dict, Literal
import logging
from logging.handlers import RotatingFileHandler
from gunicorn import glogging
from datetime import datetime, timedelta
from pathlib import Path
from flask import request


class RequestFilter(logging.Filter):
    def filter(self, record) -> Literal[True]:
        record.remote_addr = request.remote_addr if request else "N/A"
        record.host = request.host if request else "N/A"
        return True


def get_custom_config(log_dir: str) -> dict[str, Any]:

    today = datetime.now().strftime("%Y-%m-%d")

    custom_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "root": {"level": "INFO", "handlers": ["console", "file_info", "file_error", "file_debug"]},
        "loggers": {
            "coyote": {
                "level": "INFO",
                "handlers": ["console", "file_info", "file_error", "file_debug"],
                "propagate": False,
                "qualname": "coyote",
            },
            "gunicorn.error": {
                "level": "INFO",
                "handlers": ["error_console", "file_error"],
                "propagate": True,
                "qualname": "gunicorn.error",
            },
            "gunicorn.access": {
                "level": "INFO",
                "handlers": ["console", "file_info"],
                "propagate": True,
                "qualname": "gunicorn.access",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "generic",
                "stream": "ext://sys.stdout",
                "filters": ["request_filter"],
            },
            "error_console": {
                "class": "logging.StreamHandler",
                "formatter": "generic",
                "stream": "ext://sys.stderr",
                "filters": ["request_filter"],
            },
            "file_info": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filters": ["request_filter"],
                "filename": f"{log_dir}/info_{today}.log",
                "maxBytes": 5 * 1024 * 1024,  # 5 MB
                "backupCount": 10,
            },
            "file_error": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filters": ["request_filter"],
                "filename": f"{log_dir}/error_{today}.log",
                "maxBytes": 5 * 1024 * 1024,  # 5 MB
                "backupCount": 10,
            },
            "file_debug": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filters": ["request_filter"],
                "filename": f"{log_dir}/debug_{today}.log",
                "maxBytes": 5 * 1024 * 1024,  # 5 MB
                "backupCount": 10,
            },
        },
        "formatters": {
            "generic": {
                "format": "%(asctime)s - [%(process)d] - [%(levelname)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "standard": {
                "format": "%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - [%(remote_addr)s] - [%(host)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
        },
        "filters": {
            "request_filter": {
                "()": RequestFilter,
            }
        },
    }

    return custom_config


def setup_gunicorn_logging(log_dir: str) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    glogging.dictConfig(get_custom_config(log_dir))


def setup_app_logging(log_dir: str) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(get_custom_config(log_dir))


def custom_logging(log_dir: str, gunicorn_logging: bool = False) -> None:
    if gunicorn_logging:
        setup_gunicorn_logging(log_dir)
    else:
        setup_app_logging(log_dir)


def delete_logs(logs_path: str) -> None:
    for log_type in ["info", "error", "debug"]:
        for i in range(11, 21):  # Consider files up to 20 days old for deletion
            old_log_file = f"{logs_path}/{log_type}_{(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')}.log"
            try:
                Path(old_log_file).unlink()
            except FileNotFoundError:
                pass
