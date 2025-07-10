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
Centralized Logging Configuration
=================================

This file contains the centralized logging configuration for the Coyote3 application,
designed to handle both application and Gunicorn logging.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from typing import Any, Dict, Literal
from flask import request
from pathlib import Path
import os
from gunicorn import glogging


# -------------------------------------------------------------------------
# Class Definitions
# -------------------------------------------------------------------------
class RequestFilter(logging.Filter):
    """
    A logging filter that adds request-specific information to log records.

    This filter adds the `remote_addr` and `host` attributes to log records,
    which are derived from the current Flask request context. If no request
    context is available, default values of "N/A" are used.
    """

    def filter(self, record) -> Literal[True]:
        """
        Filters log records to add request-specific information such as `remote_addr` and `host`.

        If a Flask request context is available, it extracts the `remote_addr` and `host` from the request.
        Otherwise, it defaults these values to "N/A".

        :param record: The log record to be filtered.
        :return: Always returns True to ensure the record is logged.
        """
        record.remote_addr = request.remote_addr if request else "N/A"
        record.host = request.host if request else "N/A"
        return True


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    CustomTimedRotatingFileHandler
    ==============================

    A custom implementation of the `TimedRotatingFileHandler` that includes
    automatic cleanup of old log files based on a specified retention period.

    Attributes:
    -----------
    days_to_keep : int
        The number of days to retain log files. Files older than this will be deleted.

    Methods:
    --------
    doRollover():
        Performs the log file rollover and triggers cleanup of old log files.

    clean_old_log_files():
        Deletes log files older than the specified retention period.
    """

    def __init__(self, *args, days_to_keep=15, **kwargs) -> None:
        """
        Initializes the CustomTimedRotatingFileHandler.

        :param args: Positional arguments passed to the parent class.
        :param days_to_keep: The number of days to retain log files. Files older than this will be deleted.
        :param kwargs: Keyword arguments passed to the parent class.
        """
        super().__init__(*args, **kwargs)
        self.days_to_keep = days_to_keep

    def doRollover(self) -> None:
        """
        Perform log file rollover and clean up old log files.

        This method first calls the parent class's `doRollover` to rotate the log file.
        After rotation, it calls `clean_old_log_files` to remove log files older than the
        configured retention period.

        Returns:
            None
        """
        super().doRollover()
        self.clean_old_log_files()

    def clean_old_log_files(self) -> None:
        """
        Removes log files older than the configured retention period.

        Calculates a cutoff date using the `days_to_keep` attribute and deletes all log files
        in the current log directory that were last modified before this cutoff.

        Raises:
            Exception: If an error occurs while deleting a log file.
        """
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


# -------------------------------------------------------------------------
# Function Definitions
# -------------------------------------------------------------------------
def get_custom_config(log_dir: str, is_production: bool) -> Dict[str, Any]:
    """
    Returns a logging configuration dictionary for the Coyote3 application.

    The configuration includes handlers, loggers, formatters, and filters,
    and is customized based on the provided log directory and environment.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool): True if running in production mode, otherwise False.

    Returns:
        Dict[str, Any]: Logging configuration dictionary.
    """
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
    """
    Sets up logging for Gunicorn.

    Configures logging for the Gunicorn server using a custom logging configuration.
    - Ensures log directories exist.
    - Applies the logging configuration for Gunicorn.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool): Whether the application is running in production mode.

    Raises:
        Exception: If an error occurs during the logging setup.
    """
    try:
        for sub in ["audit", "info", "error", "debug"]:
            (Path(log_dir) / sub).mkdir(parents=True, exist_ok=True)
        glogging.dictConfig(get_custom_config(log_dir, is_production))
    except Exception as e:
        print(f"Failed to setup gunicorn logging: {e}")
        raise


def setup_app_logging(log_dir: str, is_production: bool = False) -> None:
    """
    Sets up logging for the application.

    Configures logging using a custom configuration, ensuring log directories exist and applying the configuration.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool): Whether the application is running in production mode.

    Raises:
        Exception: If an error occurs during the logging setup.
    """
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
    """
    Configures custom logging for the application or Gunicorn.

    Parameters
    ----------
    log_dir : str
        The directory where log files will be stored.
    is_production : bool, optional
        Indicates whether the application is running in production mode.
    gunicorn_logging : bool, optional
        If True, configures logging for Gunicorn; otherwise, for the application.

    Returns
    -------
    None
    """
    if gunicorn_logging:
        setup_gunicorn_logging(log_dir, is_production)
    else:
        setup_app_logging(log_dir, is_production)


def add_unique_handlers(logger, handlers):
    """
    Add only unique handlers to a logger.

    Ensures that each handler is added to the logger only once, based on the handler's class name.

    Parameters
    ----------
    logger : logging.Logger
        The logger instance to which handlers will be added.
    handlers : list[logging.Handler]
        A list of handlers to add to the logger.

    Returns
    -------
    None
    """
    existing_handlers = {h.__class__.__name__ for h in logger.handlers}
    for handler in handlers:
        if handler.__class__.__name__ not in existing_handlers:
            logger.addHandler(handler)
            existing_handlers.add(handler.__class__.__name__)
