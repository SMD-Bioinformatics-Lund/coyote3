"""Small web-layer helpers for Flask -> API route handlers."""

from __future__ import annotations

from logging import Logger

from flask import flash

from coyote.errors.exceptions import AppError, from_api_request_error
from shared.logging import emit_audit_event

from coyote.services.api_client.base import ApiRequestError


def log_api_error(
    exc: ApiRequestError,
    *,
    logger: Logger,
    log_message: str,
    flash_message: str | None = None,
    flash_category: str = "red",
) -> None:
    """Apply consistent API error logging and optional UI flash messaging."""
    logger.error("%s [status=%s]: %s", log_message, exc.status_code, exc)
    emit_audit_event(
        source="web",
        action="upstream_api_error",
        status="error" if (exc.status_code or 500) >= 500 else "failed",
        severity="error" if (exc.status_code or 500) >= 500 else "warning",
        status_code=exc.status_code,
        message=log_message,
        details=str(exc),
    )
    if flash_message:
        flash(_compose_flash_message(flash_message, exc), flash_category)


def raise_page_load_error(
    exc: ApiRequestError,
    *,
    logger: Logger,
    log_message: str,
    summary: str,
    not_found_summary: str | None = None,
) -> None:
    """Log an upstream API failure and raise a web-facing page error."""
    log_api_error(exc, logger=logger, log_message=log_message)
    raise from_api_request_error(
        exc,
        summary=summary,
        not_found_summary=not_found_summary,
    )


def flash_api_success(message: str) -> None:
    """Flash a standardized success message."""
    flash(message, "green")


def flash_api_failure(message: str, exc: ApiRequestError, *, category: str = "red") -> None:
    """Flash a standardized user-facing failure message."""
    flash(_compose_flash_message(message, exc), category)


def app_error_response(status_code: int, message: str, details: str | None = None) -> AppError:
    """Create a typed web application error for standardized error pages."""
    return AppError(status_code, message, details)


def _compose_flash_message(message: str, exc: ApiRequestError) -> str:
    """Handle  compose flash message.

    Args:
            message: Message.
            exc: Exc.

    Returns:
            The  compose flash message result.
    """
    status_suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
    return f"{message}{status_suffix}"
