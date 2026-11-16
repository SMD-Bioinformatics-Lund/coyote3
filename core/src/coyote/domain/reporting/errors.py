# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Persistence errors that require report-artifact reconciliation."""

from coyote.domain.exceptions import AppError


class ReportCommitUncertain(AppError):
    """The storage provider could not confirm whether the report transaction committed."""

    def __init__(self) -> None:
        """Initialize a 503 error requiring saved-report verification before retrying."""
        super().__init__(
            503, "Report commit could not be confirmed. Verify saved reports before retrying."
        )
