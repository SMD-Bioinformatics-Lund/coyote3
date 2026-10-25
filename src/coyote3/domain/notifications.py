"""Persistence contract for recipient-scoped inbox and email delivery."""

from typing import Any, Protocol


class NotificationRepository(Protocol):
    """Store messages and per-recipient delivery state without exposing database handles."""

    def claim_email(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Lease one pending broadcast email, recovering abandoned attempts."""
        ...

    def finish_email(self, notification_id: Any, lease_id: str, *, state: str) -> None:
        """Record a leased recipient's terminal outcome without overwriting another worker."""
        ...

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        """Look up a notification for ownership checks, including expired records."""
        ...

    def list_sent(self, username: str, *, limit: int = 200) -> list[dict[str, Any]]:
        """Return the sender's broadcasts, including withdrawn and expired records."""
        ...

    def withdraw(self, notification_id: str, username: str) -> bool:
        """Atomically withdraw a sender-owned broadcast without deleting its record."""
        ...

    def create(self, document: dict[str, Any]) -> str:
        """Insert a notification, preserving existing state for a stable source-event ID."""
        ...

    def list_for_user(
        self, username: str, *, limit: int = 200, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List a user's undismissed notifications with newest messages first."""
        ...

    def mark_read(self, notification_id: str, username: str) -> bool:
        """Add a user to a visible notification's read set and update its timestamp."""
        ...

    def mark_unread(self, notification_id: str, username: str) -> bool:
        """Remove only this recipient's read marker from a visible notification."""
        ...

    def mark_all_read(self, username: str) -> int:
        """Mark all visible notifications read by a user in one transaction."""
        ...

    def dismiss(self, notification_id: str, username: str) -> bool:
        """Add a user to a visible notification's dismissal set."""
        ...

    def dismiss_all(self, username: str) -> int:
        """Dismiss all currently visible messages for a user in one transaction."""
        ...
