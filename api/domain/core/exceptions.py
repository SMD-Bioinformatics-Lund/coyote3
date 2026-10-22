"""Application errors carrying status and detail fields for HTTP translation."""

from typing import Any


class AppError(Exception):
    """Custom application error for centralized error handling."""

    def __init__(
        self,
        status_code: int,
        message: str,
        details: Any = None,
        *,
        category: str | None = None,
        hint: str | None = None,
    ) -> None:
        """Carry a safe client-facing error through application and HTTP boundaries.

        Args:
            status_code: HTTP status assigned by the centralized exception handler.
            message: Client-facing explanation without private implementation details.
            details: Optional structured validation context; None omits additional detail.
            category: Optional stable error category used by clients.
            hint: Optional corrective action suitable for the caller.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details  # Optional additional info
        self.category = category
        self.hint = hint

    @property
    def detail(self) -> dict[str, Any]:
        """Return the JSON error detail shape used by HTTP translation."""
        return {
            "status": self.status_code,
            "error": self.message,
            "details": self.details,
            "category": self.category,
            "hint": self.hint,
        }
