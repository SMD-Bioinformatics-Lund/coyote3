"""Web-owned exception types for Flask error handlers and page failures."""

from __future__ import annotations

from coyote.services.api_client.base import ApiRequestError


class AppError(Exception):
    """Application-level error used by web routes and handlers.

    Args:
        status_code: HTTP status code to return.
        message: User-facing summary.
        details: Optional detailed description.
    """

    def __init__(self, status_code: int, message: str, details: str | None = None):
        """__init__.

        Args:
                status_code: Status code.
                message: Message.
                details: Details. Optional argument.
        """
        super().__init__(message)
        self.status_code = int(status_code)
        self.message = message
        self.details = details


class PageLoadError(AppError):
    """Raised when a full-page web view cannot be rendered safely."""


class UpstreamServiceError(AppError):
    """Raised when an upstream API dependency prevents page rendering."""


class ResourceNotFoundError(AppError):
    """Raised when the requested resource does not exist."""


def from_api_request_error(
    exc: ApiRequestError,
    *,
    summary: str,
    not_found_summary: str | None = None,
    default_status: int = 502,
) -> AppError:
    """Translate an API client failure into a user-facing web error."""
    status_code = int(exc.status_code or default_status)
    details = str(exc)
    if status_code == 404:
        return ResourceNotFoundError(404, not_found_summary or summary, details)
    if status_code in {401, 403}:
        return AppError(status_code, summary, details)
    if status_code >= 500:
        return UpstreamServiceError(status_code, summary, details)
    return PageLoadError(status_code, summary, details)
