# Copyright (c) 2025 Coyote3 Project Authors
# All rights reserved.
#
# This source file is part of the Coyote3 codebase.
# The Coyote3 project provides a framework for genomic data analysis,
# interpretation, reporting, and clinical diagnostics.
#
# Unauthorized use, distribution, or modification of this software or its
# components is strictly prohibited without prior written permission from
# the copyright holders.

"""
Centralized Logging Configuration
=================================

This file contains the centralized logging configuration for the Coyote3 application,
designed to handle both application and Gunicorn logging with daily rotation,
UTC timestamps, single-folder log storage, and optional log cleanup.
"""

import logging
import logging.config
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from typing import Any, Dict, Literal
from flask import request, has_request_context
from flask_login import current_user
from pathlib import Path
import os
from gunicorn import glogging


class RequestFilter(logging.Filter):
    """
    A logging filter that enriches log records with Flask request and user context.

    Adds the following fields to each log record:
    - `remote_addr`: The remote IP address of the client making the request, or "N/A" if unavailable.
    - `host`: The host header of the request, or "N/A" if unavailable.
    - `user`: The username of the currently authenticated user, or "-" if not authenticated.

    This enables log formatters to include request and user information in log outputs,
    improving traceability and auditability in a Flask application.
    """
    def filter(self, record) -> Literal[True]:
        """
        Enriches the log record with request and user context.
        Args:
            record (logging.LogRecord): The log record to be enriched.
        Returns:
            True: Always returns True to allow the log record to be processed.
        """
        if has_request_context():
            record.remote_addr = request.remote_addr or "N/A"
            record.host = request.host or "N/A"
            record.user = current_user.username if current_user.is_authenticated else "-"
        else:
            record.remote_addr = "N/A"
            record.host = "N/A"
            record.user = "-"
        return True


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Extends TimedRotatingFileHandler to add support for:
    - UTC rotation
    - UTF-8 encoding
    - Log cleanup based on days_to_keep and delete_old
    """
    def __init__(self, *args, days_to_keep=15, log_dir="logs", delete_old=True, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("utc", True)
        self.days_to_keep = days_to_keep
        self.delete_old = delete_old
        self.log_dir = log_dir
        super().__init__(*args, **kwargs)

    def _update_filename(self):
        now = datetime.utcnow()
        self.baseFilename = get_utc_log_path(self.log_dir, self.level_name, now)
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)

    def doRollover(self):
        """
        Perform the rollover operation, which includes:
        - Rotating the log file based on time
        - Cleaning up old log files if delete_old is True
        """
        super().doRollover()
        self._update_filename()
        if self.delete_old:
            self.clean_old_log_files()

    def clean_old_log_files(self):
        """
        Deletes log files older than days_to_keep from the log directory.
        This method navigates up to the YYYY level directory and removes
        any log files that are older than the specified number of days.
        """
        cutoff = datetime.utcnow() - timedelta(days=self.days_to_keep)
        root_dir = Path(self.baseFilename).parents[3]  # navigate up to YYYY level
        for log_file in root_dir.rglob("*.log"):
            try:
                if datetime.utcfromtimestamp(log_file.stat().st_mtime) < cutoff:
                    os.remove(log_file)
                    logging.getLogger("coyote").info(f"Deleted old log: {log_file}")
            except Exception as e:
                logging.getLogger("coyote").error(f"Error deleting log {log_file}: {e}")


def get_utc_log_path(log_dir: str, level: str) -> str:
    """
    Generates a UTC timestamped log file path based on the provided log directory and log level.
    The log file is organized into a folder structure based on the current date (YYYY/MM/DD),
    and the filename includes the log level.
    Args:
        log_dir (str): The base directory where log files will be stored.
        level (str): The log level for the file (e.g., "info", "error", "debug", "audit").
    Returns:
        str: The full path to the log file, including the directory and filename.
    """
    now = datetime.utcnow()
    folder = Path(log_dir) / now.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    filename = now.strftime(f"%Y-%m-%d.{level}.log")
    return str(folder / filename)


def get_custom_config(log_dir: str, is_production: bool) -> Dict[str, Any]:
    """
    Generates a custom logging configuration dictionary for the Coyote3 application.
    This configuration includes:
    - Handlers for console and file logging with daily rotation
    - Formatters for standard and colorized output
    - Loggers for application, Gunicorn error, and access logs
    - A filter to enrich log records with request and user context
    Args:
        log_dir (str): The directory where log files will be stored.
        is_production (bool): Flag indicating if the application is in production mode.
    Returns:
        Dict[str, Any]: A dictionary containing the logging configuration.
    """
    handlers = {
        "console": {
            "class": "colorlog.StreamHandler",
            "formatter": "colorized",
            "stream": "ext://sys.stdout",
            "filters": ["request_filter"],
        },
        "file_info": {
            "level": "INFO",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": get_utc_log_path(log_dir, "info"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 90,
            "delete_old": True,
        },
        "file_error": {
            "level": "ERROR",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": get_utc_log_path(log_dir, "error"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 90,
            "delete_old": True,
        },
        "audit": {
            "level": "INFO",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": get_utc_log_path(log_dir, "audit"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 180,
            "delete_old": True,
        },
    }

    if not is_production:
        handlers["file_debug"] = {
            "level": "DEBUG",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "filename": get_utc_log_path(log_dir, "debug"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 15,
            "delete_old": True,
        }

    loggers = {
        "coyote": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "file_info", "file_error"] + (["file_debug"] if not is_production else []),
            "propagate": False,
        },
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console", "file_error"],
            "propagate": True,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": True,
        },
        "audit": {
            "level": "INFO",
            "handlers": ["audit", "console"],
            "propagate": False,
        },
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "loggers": loggers,
        "handlers": handlers,
        "root": {
            "level": "INFO",
            "handlers": ["console", "file_info", "file_error"] + (["file_debug"] if not is_production else []),
        },
        "formatters": {
            "standard": {
                "format": "%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - [%(remote_addr)s] - [%(host)s] - [%(user)s] - %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "colorized": {
                "format": "%(log_color)s%(asctime)s - [%(process)d] - [%(name)s] - [%(levelname)s] - [%(remote_addr)s] - [%(host)s] - [%(user)s] - %(message)s",
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
            },
        },
    }


def setup_app_logging(log_dir: str, is_production: bool = False):
    """
    Sets up the application logging configuration using a custom configuration dictionary.
    Args:
        log_dir (str): The directory where log files will be stored.
        is_production (bool): Flag indicating if the application is in production mode.
    Returns:
        None
    """
    logging.config.dictConfig(get_custom_config(log_dir, is_production))


def setup_gunicorn_logging(log_dir: str, is_production: bool = False):
    """
    Sets up the Gunicorn logging configuration using a custom configuration dictionary.
    Args:
        log_dir (str): The directory where log files will be stored.
        is_production (bool): Flag indicating if the application is in production mode.
    Returns:
        None
    """
    glogging.dictConfig(get_custom_config(log_dir, is_production))


def custom_logging(log_dir: str, is_production: bool = False, gunicorn_logging: bool = False):
    """
    Configures logging for the Coyote3 application, either for Gunicorn or the Flask app.
    Args:
        log_dir (str): The directory where log files will be stored.
        is_production (bool): Flag indicating if the application is in production mode.
        gunicorn_logging (bool): Flag indicating if Gunicorn logging should be configured.
    Returns:
        None
    """
    if gunicorn_logging:
        setup_gunicorn_logging(log_dir, is_production)
    else:
        setup_app_logging(log_dir, is_production)


def add_unique_handlers(logger, handlers):
    """
    Adds unique handlers to a logger if they are not already present.
    Args:
        logger (logging.Logger): The logger to which handlers will be added.
        handlers (list): A list of logging.Handler instances to add to the logger.
    Returns:
        None
    """
    existing_handlers = {h.__class__.__name__ for h in logger.handlers}
    for handler in handlers:
        if handler.__class__.__name__ not in existing_handlers:
            logger.addHandler(handler)
            existing_handlers.add(handler.__class__.__name__)
