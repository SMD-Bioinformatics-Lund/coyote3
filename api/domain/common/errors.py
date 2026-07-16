"""Domain error helpers."""

from __future__ import annotations

from api.domain.core.exceptions import AppError


def api_error(
    status_code: int,
    message: str,
    details: str | None = None,
    *,
    category: str | None = None,
    hint: str | None = None,
) -> AppError:
    """Build a standardized domain application error."""
    return AppError(status_code, message, details, category=category, hint=hint)


def validation_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized validation error."""
    return api_error(400, message, details, category="validation", hint=hint)


def not_found_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized not-found error."""
    return api_error(404, message, details, category="not_found", hint=hint)


def forbidden_error(message: str, details: str | None = None, *, hint: str | None = None):
    """Build a standardized forbidden/scope error."""
    return api_error(403, message, details, category="scope", hint=hint)


def setup_error(
    message: str,
    details: str | None = None,
    *,
    hint: str | None = None,
    status_code: int = 422,
):
    """Build a standardized setup/configuration error."""
    return api_error(status_code, message, details, category="setup", hint=hint)
