"""Web-owned exception types for Flask error handlers."""


class AppError(Exception):
    """Application-level error used by web routes and handlers.

    Args:
        status_code: HTTP status code to return.
        message: User-facing summary.
        details: Optional detailed description.
    """

    def __init__(self, status_code: int, message: str, details: str | None = None):
        super().__init__(message)
        self.status_code = int(status_code)
        self.message = message
        self.details = details
