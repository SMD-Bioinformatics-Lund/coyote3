"""Persistence errors that require report-artifact reconciliation."""

from api.domain.core.exceptions import AppError


class ReportCommitUncertain(AppError):
    """MongoDB could not confirm whether the report transaction committed."""

    def __init__(self):
        """Initialize a 503 error requiring saved-report verification before retrying."""
        super().__init__(
            503, "Report commit could not be confirmed. Verify saved reports before retrying."
        )
