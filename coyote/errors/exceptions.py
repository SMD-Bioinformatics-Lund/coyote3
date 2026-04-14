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
    payload = exc.payload if isinstance(exc.payload, dict) else {}
    headline = str(payload.get("error") or str(exc) or summary).strip() or summary
    detail_lines: list[str] = []
    raw_details = str(payload.get("details") or "").strip()
    raw_hint = str(payload.get("hint") or "").strip()
    if raw_details and raw_details != headline:
        detail_lines.append(raw_details)
    if raw_hint:
        detail_lines.append(f"Hint: {raw_hint}")
    details = "\n\n".join(detail_lines) if detail_lines else str(exc)
    if status_code == 404:
        return ResourceNotFoundError(404, headline or not_found_summary or summary, details)
    if status_code in {401, 403}:
        return AppError(status_code, headline or summary, details)
    if 400 <= status_code < 500:
        return PageLoadError(status_code, headline or summary, details)
    if status_code >= 500:
        return UpstreamServiceError(status_code, summary, details)
    return PageLoadError(status_code, summary, details)
