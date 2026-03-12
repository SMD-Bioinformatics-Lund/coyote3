
class AppError(Exception):
    """Custom application error for centralized error handling."""

    def __init__(self, status_code, message, details=None):
        """Handle __init__.

        Args:
                status_code: Status code.
                message: Message.
                details: Details. Optional argument.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details  # Optional additional info
