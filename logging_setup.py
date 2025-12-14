#  Copyright (c) 2025 Coyote3 Project Authors All rights reserved. \n
#  This source file is part of the Coyote3 codebase. The Coyote3 project provides a framework for genomic data analysis, interpretation, reporting, and clinical diagnostics. \n
#  Unauthorized use, distribution, or modification of this software or its components is strictly prohibited without prior written permission from the copyright holders.
#

import logging
import logging.config
from logging.handlers import TimedRotatingFileHandler, QueueHandler, QueueListener
from datetime import datetime, timedelta
from typing import Any, Dict, Literal
from flask import request, has_request_context
from flask_login import current_user
from pathlib import Path
from gunicorn import glogging
import queue
import atexit
import os

# Global queue for asynchronous logging
log_queue = queue.Queue(-1)  # Infinite size

# Listener writes logs using your existing handlers
listener = None


#### CLASS DEFINITIONS ####

class RequestFilter(logging.Filter):
    """
    Custom logging filter that injects request context information into log records.

    Adds the following fields to each log record:
    - remote_addr: The client's IP address, or "N/A" if unavailable.
    - host: The request host, or "N/A" if unavailable.
    - user: The authenticated user's username, or "-" if not authenticated.

    This filter enables enhanced log traceability for Flask applications by including user and request metadata.
    """
    def filter(self, record) -> Literal[True]:
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
    CustomTimedRotatingFileHandler is a logging handler that rotates log files based on time intervals
    (e.g., daily at midnight) and uses UTC timestamps for file naming. It supports automatic creation
    of log directories, optional deletion of old log files, and flexible log file organization (nested
    or flat folders).This handler is useful for applications requiring organized, time-based log rotation
    and retention management in UTC.
    """
    def __init__(self, *args, level_name=None, days_to_keep=0, log_dir="logs",
                 delete_old=False, subdir=None, flat=False, **kwargs):

        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("utc", True)

        self.level_name = level_name or "info"
        self.log_dir = log_dir
        self.subdir = subdir
        self.flat = flat
        self.days_to_keep = days_to_keep
        self.delete_old = delete_old

        filename = get_utc_log_path(self.log_dir, self.level_name, subdir=self.subdir, flat=self.flat)
        kwargs["filename"] = filename
        super().__init__(*args, **kwargs)

    def emit(self, record) -> None:
        """
        Emit a log record, ensuring the log file exists and is ready for writing.

        This method overrides the base emit to:
        - Ensure the log file's parent directory exists.
        - Reopen the stream if the log file does not exist.
        - Perform log rotation if needed.
        - Write the log record to the file.

        Args:
            record: The log record to be emitted.

        Raises:
            Exception: If file operations fail, a warning is printed.
        """
        try:
            Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
            if not os.path.exists(self.baseFilename):
                self._reopen_stream()
            if self.shouldRollover(record):
                self.doRollover()
        except Exception as e:
            print(f"[Logging Warning] Failed during emit: {e}")
        super().emit(record)

    def _update_filename(self) -> None:
        """
        Update the base filename for the log file using the current UTC time and handler configuration.

        This method generates a new log file path based on:
        - Current UTC time
        - Log directory
        - Log level name
        - Optional subdirectory or flat folder structure

        It ensures the target directory exists before updating the handler's base filename.
        """
        self.baseFilename = get_utc_log_path(self.log_dir, self.level_name, subdir=self.subdir, flat=self.flat)
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)

    def _reopen_stream(self) -> None:
        """
        Reopen the log file stream.

        This method closes the current stream if open, updates the log file path using the latest UTC
        timestamp and handler configuration, and opens a new stream for writing. It ensures that log
        records are written to the correct file, especially after rotation or file deletion events.
        """
        if self.stream:
            self.stream.close()
        self._update_filename()
        self.stream = self._open()

    def doRollover(self) -> None:
        """
        Perform a rollover of the log file.

        This method rotates the log file based on the configured time interval (e.g., daily at midnight).
        After rotation, it updates the base filename to a new UTC-timestamped path and deletes old log
        files if retention is enabled.

        Returns:
            None
        """
        super().doRollover()
        self.baseFilename = get_utc_log_path(self.log_dir, self.level_name, subdir=self.subdir, flat=self.flat)
        if self.delete_old and self.days_to_keep > 0:
            self.clean_old_log_files()

    def clean_old_log_files(self) -> None:
        """
        Deletes log files older than the specified retention period (`days_to_keep`).

        This method scans the log directory recursively for files ending with `.log`.
        If a file's last modification time is older than the UTC cutoff date (`days_to_keep` days ago),
        it attempts to delete the file. Errors during deletion are logged to the `coyote` logger.
        """
        cutoff = datetime.utcnow() - timedelta(days=self.days_to_keep)
        log_root = Path(self.log_dir)
        for file in log_root.rglob("*.log"):
            try:
                if datetime.utcfromtimestamp(file.stat().st_mtime) < cutoff:
                    file.unlink()
            except Exception as e:
                logging.getLogger("coyote").error(f"Failed to delete log file {file}: {e}")


#### FUNCTION DEFINITIONS ####
def get_utc_log_path(log_dir: str, level: str, now: datetime | None = None, subdir: str | None = None, flat: bool = False) -> str:
    """
    Generate a UTC-timestamped log file path.

    Args:
        log_dir (str): Base logs directory, e.g., logs/dev or logs/prod
        level (str): Level or category of log (used in filename)
        now (datetime | None): Datetime for naming
        subdir (str | None): Optional subfolder like 'audit'
        flat (bool): If True, do not create nested YYYY/MM/DD folders

    Returns:
        str: Full file path
    """
    if now is None:
        now = datetime.utcnow()

    base_path = Path(log_dir)
    if subdir:
        base_path = base_path / subdir

    if not flat:
        folder = base_path / now.strftime("%Y/%m/%d")
    else:
        folder = base_path

    folder.mkdir(parents=True, exist_ok=True)
    filename = now.strftime(f"%Y-%m-%d.{level}.log")
    return str(folder / filename)

def stop_async_logging() -> None:
    """
    Stops the asynchronous logging listener and cleans up resources.

    This function checks if the global `listener` is active and stops it, ensuring all queued log records are processed before shutdown.
    It should be called during application shutdown to ensure graceful termination of asynchronous logging.

    Returns:
        None
    """
    global listener
    if listener:
        listener.stop()

def setup_async_logging(log_dir: str, is_production: bool = False) -> None:
    """
    Initializes asynchronous logging using a QueueListener and QueueHandler.

    This function sets up logging so that log records are placed into a queue and processed asynchronously.
    It loads the logging configuration, collects the appropriate handlers, starts a QueueListener, and replaces
    the root logger's handlers with a QueueHandler. This improves logging performance and reliability in
    multi-threaded or production environments.
    """
    global listener

    # Load config first
    config = get_custom_config(log_dir, is_production)
    logging.config.dictConfig(config)

    # Get all handlers you want to delegate to
    handler_names = ["file_info", "file_error", "fallback_file"]
    if not is_production:
        handler_names.append("file_debug")
    handler_names.append("audit")  # add others if needed

    # Gather handlers from config
    handlers = []
    for name in handler_names:
        handler = logging.getLogger().handlers[0]  # fallback if name not found
        for hname, hconf in config["handlers"].items():
            if hname == name:
                try:
                    h = logging._handlers[hname]
                except Exception:
                    h = None
                if h:
                    handlers.append(h)
    # Setup listener
    listener = QueueListener(log_queue, *handlers)
    listener.start()

    # Replace handlers on root with QueueHandler
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(QueueHandler(log_queue))

    # Register cleanup to stop listener on exit
    atexit.register(stop_async_logging)

def get_custom_config(log_dir: str, is_production: bool) -> Dict[str, Any]:
    """
    Generates and returns a custom logging configuration dictionary for the application.

    This configuration includes handlers, formatters, filters, and logger settings tailored for both production and development environments.
    It supports asynchronous logging, file rotation, request context enrichment, and colorized console output.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool): If True, configures for production logging; otherwise, enables debug handlers and settings.

    Returns:
        Dict[str, Any]: A dictionary suitable for use with logging.config.dictConfig.
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
            "level_name": "info",
            "log_dir": log_dir,
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 0,
            "delete_old": False,
        },
        "file_error": {
            "level": "WARNING",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "level_name": "error",
            "log_dir": log_dir,
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 0,
            "delete_old": False,
        },
        "audit": {
            "level": "INFO",
            "()": CustomTimedRotatingFileHandler,
            "filters": ["request_filter"],
            "formatter": "standard",
            "level_name": "audit",
            "log_dir": log_dir,
            "subdir": "audit",
            "flat": True,
            "when": "midnight",
            "interval": 1,
            "days_to_keep": 180,
            "delete_old": True,
        },
        "werkzeug": {
            "level": "INFO",
            "()": CustomTimedRotatingFileHandler,
            "formatter": "standard",
            "level_name": "werkzeug",
            "log_dir": log_dir,
            "subdir": "werkzeug",
            "flat": True,
            "when": "midnight",
            "interval": 1,
            "days_to_keep": 180,
            "delete_old": True,
        },
        "gunicorn": {
            "level": "INFO",
            "()": CustomTimedRotatingFileHandler,
            "formatter": "standard",
            "level_name": "gunicorn",
            "log_dir": log_dir,
            "subdir": "gunicorn",
            "flat": True,
            "when": "midnight",
            "interval": 1,
            "days_to_keep": 180,
            "delete_old": True,
        },
        "flask": {
            "level": "INFO",
            "()": CustomTimedRotatingFileHandler,
            "formatter": "standard",
            "level_name": "flask",
            "log_dir": log_dir,
            "subdir": "flask",
            "flat": True,
            "when": "midnight",
            "interval": 1,
            "days_to_keep": 180,
            "delete_old": True,
        },
        "fallback_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "filename": str(Path(log_dir) / "fallback.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 2,
            "encoding": "utf-8",
        },
    }

    if not is_production:
        handlers["file_debug"] = {
            "level": "DEBUG",
            "()": "logging_setup.CustomTimedRotatingFileHandler",
            "formatter": "standard",
            "filters": ["request_filter"],
            "level_name": "debug",
            "log_dir": log_dir,
            "when": "midnight",
            "interval": 1,
            "backupCount": 0,
            "days_to_keep": 0,
            "delete_old": False,
        }

    loggers = {
        "coyote": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "file_info", "file_error"] + (["file_debug"] if not is_production else []),
            "propagate": False,
        },
        "werkzeug": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "werkzeug"],
            "propagate": False,
        },
        "gunicorn": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "gunicorn"],
            "propagate": True,
        },
        "flask": {
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "flask"],
            "propagate": False,
        },
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console", "file_error"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": False,
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
            "level": "DEBUG" if not is_production else "INFO",
            "handlers": ["console", "file_info", "file_error", "fallback_file"] + (["file_debug"] if not is_production else []),
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

def setup_app_logging(log_dir: str, is_production: bool = False) -> None:
    """
    Initializes application logging using a custom configuration.

    This function sets up logging for the application by applying a configuration
    generated by `get_custom_config`. It configures handlers, formatters, filters,
    and logger settings for both production and development environments.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool, optional): If True, configures for production logging;
            otherwise, enables debug handlers and settings. Defaults to False.

    Returns:
        None
    """
    logging.config.dictConfig(get_custom_config(log_dir, is_production))

def setup_gunicorn_logging(log_dir: str, is_production: bool = False) -> None:
    """
    Initializes Gunicorn logging using a custom configuration.

    Args:
        log_dir (str): Directory where log files will be stored.
        is_production (bool, optional): If True, configures for production logging;
            otherwise, enables debug handlers and settings. Defaults to False.

    Returns:
        None
    """
    glogging.dictConfig(get_custom_config(log_dir, is_production))


def custom_logging(log_dir: str, is_production: bool = False, gunicorn_logging: bool = False) -> None:
    """
    Initializes custom logging for the application.

    Sets up logging based on the provided parameters, supporting different configurations for production and development environments, and enabling Gunicorn logging if specified.

    Parameters:
        log_dir (str): Directory where log files will be stored.
        is_production (bool, optional): If True, configures for production logging; otherwise, enables debug handlers and settings. Defaults to False.
        gunicorn_logging (bool, optional): If True, sets up logging for Gunicorn. Defaults to False.

    Returns:
        None
    """
    if gunicorn_logging:
        setup_async_logging(log_dir, is_production)
    else:
        setup_app_logging(log_dir, is_production)

    logging.getLogger("coyote").info(
        f"Logging initialized [Production: {is_production}] [Gunicorn: {gunicorn_logging}]")

def add_unique_handlers(logger, handlers) -> None:
    """
    Adds handlers to a logger only if their class type is not already present.

    Args:
        logger: The logger instance to which handlers will be added.
        handlers: An iterable of handler instances to add.

    This prevents duplicate handler types from being attached to the logger.
    """
    existing_handlers = {h.__class__.__name__ for h in logger.handlers}
    for handler in handlers:
        if handler.__class__.__name__ not in existing_handlers:
            logger.addHandler(handler)
            existing_handlers.add(handler.__class__.__name__)
