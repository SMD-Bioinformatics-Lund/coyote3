class AppError(Exception):
    """Custom application error for centralized error handling."""

    def __init__(self, status_code, message, details=None, *, category=None, hint=None):
        """__init__.

        Args:
                status_code: Status code.
                message: Message.
                details: Details. Optional argument.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details  # Optional additional info
        self.category = category
        self.hint = hint

    @property
    def detail(self):
        """Return the JSON error detail shape used by HTTP translation."""
        return {
            "status": self.status_code,
            "error": self.message,
            "details": self.details,
            "category": self.category,
            "hint": self.hint,
        }
