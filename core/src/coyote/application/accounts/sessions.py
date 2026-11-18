# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Persistence boundary for credential-free login-session counts."""

from typing import Protocol

from coyote.contracts.auth import SessionActivitySummary


class SessionActivityRepository(Protocol):
    """Read session activity using current account and credential validity."""

    def activity_summary(self, *, recent_activity_seconds: int) -> SessionActivitySummary:
        """Count valid sessions and distinct users in the host's identity store.

        Args:
            recent_activity_seconds: Lookback window for authenticated requests.

        Returns:
            Counts excluding expired sessions, disabled or deleted accounts and
            sessions invalidated by credential changes. Reading the summary must
            not refresh sessions or expose tokens or account details.
        """
        ...
