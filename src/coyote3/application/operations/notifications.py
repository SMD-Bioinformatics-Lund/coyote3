"""Recipient-scoped notification and broadcast application operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.contracts.notifications import (
    NotificationBroadcastRequest,
)

if TYPE_CHECKING:
    from coyote3.application.notifications.service import NotificationService


class Notifications:
    """Notifications attributed to the current verified recipient or sender."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], NotificationService]
    ) -> None:
        """Bind current-identity authorization and the notification implementation."""
        self._runtime, self._service = runtime, service

    def inbox(self, *, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        """Return only notifications visible to the authenticated user.

        Args:
            limit: Maximum inbox rows; defaults to 200 and the service bounds it to 1–500.
            offset: Zero-based inbox offset; negative values are clamped to zero.

        Returns:
            Visible notifications, unread counts and inbox pagination.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().inbox(user=actor, limit=limit, offset=offset)

        return self._runtime.execute("notifications.inbox", None, run)

    def mark_all_read(self) -> dict[str, Any]:
        """Mark every visible notification as read for the authenticated user.

        Returns:
            Acknowledgement and the number of visible notifications marked read.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().mark_all_read(username=actor.username)

        return self._runtime.execute("notifications.mark_all_read", None, run)

    def mark_read(self, *, notification_id: str) -> dict[str, Any]:
        """Mark one visible notification as read for the authenticated user.

        Args:
            notification_id: Saved notification identifier; recipient/sender ownership is checked.

        Returns:
            Acknowledgement of the recipient-scoped read-state update.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().mark_read(
                notification_id=notification_id, username=actor.username
            )

        return self._runtime.execute("notifications.mark_read", None, run)

    def mark_unread(self, *, notification_id: str) -> dict[str, Any]:
        """Mark one visible notification unread for the authenticated recipient.

        Args:
            notification_id: Saved notification identifier; recipient/sender ownership is checked.

        Returns:
            Acknowledgement of the recipient-scoped unread-state update.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().mark_unread(
                notification_id=notification_id, username=actor.username
            )

        return self._runtime.execute("notifications.mark_unread", None, run)

    def dismiss_all(self) -> dict[str, Any]:
        """Dismiss every visible notification for the authenticated user.

        Returns:
            Acknowledgement and the number of recipient-visible notifications dismissed.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().dismiss_all(username=actor.username)

        return self._runtime.execute("notifications.dismiss_all", None, run)

    def dismiss(self, *, notification_id: str) -> dict[str, Any]:
        """Clear a personal notification, or withdraw a sender-owned broadcast for everyone.

        Args:
            notification_id: Saved notification identifier; recipient/sender ownership is checked.

        Returns:
            Acknowledgement of personal dismissal or sender-authorized broadcast withdrawal.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().dismiss(notification_id=notification_id, username=actor.username)

        return self._runtime.execute("notifications.dismiss", None, run)

    def sent(self) -> dict[str, Any]:
        """List the authenticated sender's broadcasts, including their expiry and withdrawal state.

        Returns:
            Broadcasts owned by the current sender, including expiry and withdrawal state.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().sent(username=actor.username)

        return self._runtime.execute("notifications.sent", ("notification.broadcast:create",), run)

    def recipient_options(self) -> dict[str, Any]:
        """Return active accounts and populated roles available for broadcasts.

        Returns:
            Active account and role choices available for an authorized broadcast.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().recipient_options()

        return self._runtime.execute(
            "notifications.recipient_options", ("notification.broadcast:create",), run
        )

    def broadcast(self, *, payload: NotificationBroadcastRequest) -> dict[str, Any]:
        """Publish an application message to all, role-matched, or selected active users.

        Args:
            payload: Message, audience selection and delivery options validated by the broadcast contract.

        Returns:
            Saved broadcast identity and the existing delivery outcome.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return self._service().broadcast(payload=payload.model_dump(), actor=actor)

        return self._runtime.execute(
            "notifications.broadcast", ("notification.broadcast:create",), run
        )
