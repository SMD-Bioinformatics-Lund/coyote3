"""Shared logging helpers for application and audit logging."""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.logging_setup import custom_logging

_LOGGING_CONFIGURED: set[tuple[str, bool, bool]] = set()


def get_logger(name: str) -> logging.Logger:
    """Return an application logger by name.

    Args:
        name: Logger name used with Python's standard logging registry.

    Returns:
        The configured ``logging.Logger`` instance for ``name``.
    """
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    """Return the dedicated audit logger.

    Returns:
        The ``audit`` logger used for structured governance and trace events.
    """
    return logging.getLogger("audit")


def ensure_logging_configured(
    log_dir: str, *, is_production: bool, gunicorn_logging: bool = False
) -> None:
    """Configure repository logging once for the requested runtime mode.

    Args:
        log_dir: Base directory where file-backed logs should be written.
        is_production: Whether production logging settings should be applied.
        gunicorn_logging: Whether Gunicorn-specific logging integration should
            be enabled.

    Returns:
        ``None``. The function configures process-wide logging as a side effect.
    """
    key = (str(log_dir), bool(is_production), bool(gunicorn_logging))
    if key in _LOGGING_CONFIGURED:
        return
    custom_logging(str(log_dir), is_production, gunicorn_logging=gunicorn_logging)
    _LOGGING_CONFIGURED.add(key)


def emit_audit_event(
    *,
    source: str,
    action: str,
    status: str,
    severity: str | None = None,
    message: str | None = None,
    **fields: Any,
) -> None:
    """Emit a structured audit event to the audit logger.

    Args:
        source: Logical subsystem emitting the event, such as ``api`` or
            ``web``.
        action: Event action name, for example ``request`` or ``mutation``.
        status: Outcome status for the event.
        severity: Optional explicit log severity. When omitted, severity is
            derived from ``status``.
        message: Optional human-readable summary for operators.
        **fields: Additional structured fields to embed in the audit payload.

    Severity defaults to a reasonable level derived from status:

    - `error` for `error`
    - `warning` for `failed` or `denied`
    - `info` otherwise

    Returns:
        ``None``. The event is emitted to the configured audit logger.
    """
    event = {
        "source": source,
        "action": action,
        "status": status,
        "message": message,
        **fields,
    }
    logger = get_audit_logger()
    payload = json.dumps(event, default=str)
    level = (severity or _severity_from_status(status)).lower()
    if level == "error":
        logger.error(payload)
    elif level == "warning":
        logger.warning(payload)
    else:
        logger.info(payload)


def _severity_from_status(status: str) -> str:
    """Map an audit status value to the default log severity.

    Args:
        status: Audit status string.

    Returns:
        The default severity name used when no explicit severity is supplied.
    """
    normalized = (status or "").strip().lower()
    if normalized == "error":
        return "error"
    if normalized in {"failed", "denied"}:
        return "warning"
    return "info"
