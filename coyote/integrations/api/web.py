"""Small web-layer helpers for Flask -> API route handlers."""

from __future__ import annotations

from logging import Logger

from flask import flash

from coyote.integrations.api.api_client import ApiRequestError


def log_api_error(
    exc: ApiRequestError,
    *,
    logger: Logger,
    log_message: str,
    flash_message: str | None = None,
    flash_category: str = "red",
) -> None:
    """Apply consistent API error logging and optional UI flash messaging."""
    logger.error("%s: %s", log_message, exc)
    if flash_message:
        flash(flash_message, flash_category)
