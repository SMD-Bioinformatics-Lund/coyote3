import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from typing import Any, Dict, Literal
from flask import request
from pathlib import Path
import os
from gunicorn import glogging


class RequestFilter(logging.Filter):
    def filter(self, record) -> Literal[True]:
        record.remote_addr = request.remote_addr if request else "N/A"
        record.host = request.host if request else "N/A"
        return True


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, *args, days_to_keep=15, **kwargs):
        super().__init__(*args, **kwargs)
        self.days_to_keep = days_to_keep

    def doRollover(self):
        super().doRollover()
        self.clean_old_log_files()

    def clean_old_log_files(self):
        cutoff = datetime.now() - timedelta(days=self.days_to_keep)
        log_dir = Path(self.baseFilename).parent

        # 🔥 Match everything that starts with the same base filename
        base_prefix = Path(self.baseFilename).stem  # e.g., '2025-04-09'
        for log_file in log_dir.glob(f"{base_prefix}*"):
            if (
                log_file.is_file()
                and log_file
                != Path(self.baseFilename)  # Don't delete current log
                and datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff
            ):
                try:
                    os.remove(log_file)
                    print(f"Deleted old log file: {log_file}")
                except Exception as e:
                    print(f"Error deleting file {log_file}: {e}")


def get_custom_config(log_dir: str, is_production: bool) -> Dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")

    handlers = {
        "console": {
            "class": "colorlog.StreamHandler",
            "formatter": "colorized",
            "stream": "ext://sys.stdout",
            "filters": ["request_filter"],
        },
        "error_console": {
            "class": "colorlog.StreamHandler",
            "formatter": "colorized",
            "stream": "ext://sys.stderr",
            "filters": ["request_filter"],
        },
        "file_info": {
            "level": "INFO",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": f"{log_dir}/info/{today}.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 30,
        },
        "file_error": {
            "level": "ERROR",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": f"{log_dir}/error/{today}.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,  # let days_to_keep handle deletion
            "days_to_keep": 30,
        },
        "audit": {
            "level": "INFO",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": f"{log_dir}/audit/{today}.log",
            "when": "midnight",  # rotate daily
            "interval": 1,
            "backupCount": 0,  # let days_to_keep handle deletion
            "days_to_keep": 180,  # or 365, depending on org policy
        },
    }

    if not is_production:
        handlers["file_debug"] = {
            "level": "DEBUG",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": f"{log_dir}/debug/{today}.log",
            "when": "midnight",
            "backupCount": 15,
            "days_to_keep": 15,
        }

    loggers = {
        "coyote": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "file_info", "file_error"]
            + (["file_debug"] if not is_production else []),
            "propagate": False,
            "qualname": "coyote",
        },
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console", "file_error"],
            "propagate": True,
            "qualname": "gunicorn.error",
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": True,
            "qualname": "gunicorn.access",
        },
        "audit": {
            "level": "INFO",
            "handlers": ["audit", "console"],
            "propagate": False,
            "qualname": "audit",
        },
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "root": {
            "level": "INFO",
            "handlers": ["console", "file_info", "file_error"]
            + (["file_debug"] if not is_production else []),
        },
        "loggers": loggers,
        "handlers": handlers,
        "formatters": {
            "generic": {
                "format": "%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "standard": {
                "format": "%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - [%(remote_addr)s] - [%(host)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "colorized": {
                "format": "%(log_color)s%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - [%(remote_addr)s] - [%(host)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "colorlog.ColoredFormatter",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            },
        },
        "filters": {
            "request_filter": {
                "()": RequestFilter,
            }
        },
    }


def setup_gunicorn_logging(log_dir: str, is_production: bool = False) -> None:
    try:
        for sub in ["audit", "info", "error", "debug"]:
            (Path(log_dir) / sub).mkdir(parents=True, exist_ok=True)
        glogging.dictConfig(get_custom_config(log_dir, is_production))
    except Exception as e:
        print(f"Failed to setup gunicorn logging: {e}")
        raise


def setup_app_logging(log_dir: str, is_production: bool = False) -> None:
    try:
        for sub in ["audit", "info", "error", "debug"]:
            (Path(log_dir) / sub).mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(get_custom_config(log_dir, is_production))
    except Exception as e:
        print(f"Failed to setup app logging: {e}")
        raise


def custom_logging(
    log_dir: str, is_production: bool = False, gunicorn_logging: bool = False
) -> None:
    if gunicorn_logging:
        setup_gunicorn_logging(log_dir, is_production)
    else:
        setup_app_logging(log_dir, is_production)


def add_unique_handlers(logger, handlers):
    existing_handlers = {h.__class__.__name__ for h in logger.handlers}
    for handler in handlers:
        if handler.__class__.__name__ not in existing_handlers:
            logger.addHandler(handler)
            existing_handlers.add(handler.__class__.__name__)
