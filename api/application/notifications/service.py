"""Recipient-scoped notification workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from api.config.contracts.application import NOTIFICATIONS
from api.domain.common.errors import api_error


class NotificationService:
    """Create and expose notifications without crossing recipient boundaries."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        retention_days: int,
        audit_service: Any | None = None,
        email_sender: Callable[..., bool] | None = None,
        inbox_url: str = "",
    ) -> "NotificationService":
        """Bind notification workflows to the store's notification and user repositories.

        Args:
            store: Provider of notification_repository and user_repository.
            retention_days: Expiry interval in days, clamped by the constructor.
            audit_service: Optional recorder for broadcast and reset events.
            email_sender: Configured SMTP sender, or None to disable broadcast email.
            inbox_url: Absolute URL to the authenticated notification inbox.

        Returns:
            Service using the supplied repositories and retention policy.
        """
        return cls(
            notification_repository=store.notification_repository,
            user_repository=store.user_repository,
            retention_days=retention_days,
            audit_service=audit_service,
            email_sender=email_sender,
            inbox_url=inbox_url,
        )

    def __init__(
        self,
        *,
        notification_repository: Any,
        user_repository: Any,
        retention_days: int,
        audit_service: Any | None = None,
        email_sender: Callable[..., bool] | None = None,
        inbox_url: str = "",
    ) -> None:
        """Configure notification persistence, recipient lookup, and expiry.

        Args:
            notification_repository: Stores notifications and recipient read states.
            user_repository: Looks up active recipients and role membership.
            retention_days: Days until expiry; falsey values use 180, with a minimum of 7.
            audit_service: Optional event recorder; None disables audit recording here.
            email_sender: Configured SMTP sender, or None to disable broadcast email.
            inbox_url: Absolute URL included in broadcast emails.
        """
        self.notification_repository = notification_repository
        self.user_repository = user_repository
        self.retention_days = max(7, int(retention_days or 180))
        self.audit_service = audit_service
        self.email_sender = email_sender
        self.inbox_url = inbox_url

    def inbox(self, *, username: str, limit: int = 200) -> dict[str, Any]:
        """List notifications visible to a recipient with per-recipient read state.

        Args:
            username: Recipient login, stripped and lowercased before lookup.
            limit: Maximum rows requested from the repository, defaulting to 200.

        Returns:
            Serialized notifications and the unread count within those rows.
        """
        normalized = self._username(username)
        rows = self.notification_repository.list_for_user(normalized, limit=limit)
        notifications = [self._serialize(item, username=normalized) for item in rows]
        return {
            "notifications": notifications,
            "unread_count": sum(1 for item in notifications if not item["read"]),
        }

    def mark_read(self, *, notification_id: str, username: str) -> dict[str, Any]:
        """Mark one notification read for the specified recipient.

        Args:
            notification_id: Notification identifier to update.
            username: Recipient login, normalized before the repository call.

        Returns:
            Success status with changed set to one.

        Raises:
            AppError: With status 404 when the repository reports no change.
        """
        changed = self.notification_repository.mark_read(notification_id, self._username(username))
        if not changed:
            raise api_error(404, "Notification not found")
        return {"status": "ok", "changed": 1}

    def mark_all_read(self, *, username: str) -> dict[str, Any]:
        """Mark the recipient's notifications read in bulk.

        Args:
            username: Recipient login, normalized before the repository call.

        Returns:
            Success status and the repository's changed count.
        """
        changed = self.notification_repository.mark_all_read(self._username(username))
        return {"status": "ok", "changed": changed}

    def dismiss(self, *, notification_id: str, username: str) -> dict[str, Any]:
        """Clear a personal message or withdraw a sender-owned broadcast for all recipients.

        Args:
            notification_id: Notification identifier to update.
            username: Recipient login, normalized before the repository call.

        Returns:
            Success status and the changed count; repeated withdrawal returns zero.

        Raises:
            AppError: With status 403 for recipient broadcast withdrawal, or 404
                when a personal message is not visible to the caller.
        """
        username = self._username(username)
        document = self.notification_repository.get_notification(notification_id)
        if document and document.get("is_broadcast") is True:
            if document.get("created_by") != username:
                raise api_error(403, "Only the sender can withdraw a broadcast")
            changed = self.notification_repository.withdraw(notification_id, username)
            if changed and self.audit_service:
                self.audit_service.record(
                    "notification.broadcast.withdrawn",
                    "Broadcast withdrawn by its sender",
                    category="administration",
                    actor=username,
                    resource_type="notification",
                    resource_id=notification_id,
                    metadata={"sender": username},
                )
            return {"status": "ok", "changed": int(changed)}
        changed = self.notification_repository.dismiss(notification_id, username)
        if not changed:
            raise api_error(404, "Notification not found")
        return {"status": "ok", "changed": 1}

    def dismiss_all(self, *, username: str) -> dict[str, Any]:
        """Dismiss the recipient's notifications in bulk.

        Args:
            username: Recipient login, normalized before the repository call.

        Returns:
            Success status and the repository's changed count.
        """
        changed = self.notification_repository.dismiss_all(self._username(username))
        return {"status": "ok", "changed": changed}

    def recipient_options(self) -> dict[str, Any]:
        """Build broadcast choices from active users and their role memberships.

        Returns:
            User identity labels and alphabetically ordered roles with user counts.
        """
        users = self.user_repository.list_active_users_for_notifications()
        role_counts: dict[str, int] = {}
        for user in users:
            for role_id in user.get("roles") or []:
                normalized_role = self._username(role_id)
                if normalized_role:
                    role_counts[normalized_role] = role_counts.get(normalized_role, 0) + 1
        return {
            "users": [
                {
                    "username": self._username(user.get("username")),
                    "name": self._display_name(user),
                    "email": str(user.get("email") or ""),
                }
                for user in users
                if self._username(user.get("username"))
            ],
            "roles": [
                {
                    "role_id": role_id,
                    "label": role_id.replace("_", " ").title(),
                    "user_count": count,
                }
                for role_id, count in sorted(role_counts.items())
            ],
        }

    def sent(self, *, username: str) -> dict[str, Any]:
        """Return sender-owned broadcasts for review and withdrawal.

        Args:
            username: Authenticated sender, normalized to a canonical login.

        Returns:
            Serialized sent messages and an unread count of zero; this list is a
            sender archive, not the recipient inbox.
        """
        username = self._username(username)
        return {
            "notifications": [
                self._serialize(row, username=username)
                for row in self.notification_repository.list_sent(username)
            ],
            "unread_count": 0,
        }

    def broadcast(self, *, payload: dict[str, Any], actor: Any) -> dict[str, Any]:
        """Create a broadcast for all active users, selected users, or role members.

        Args:
            payload: Audience (all, roles, or selected), recipients or role_ids,
                title, message, and optional tone and category.
            actor: Audit actor; its username identifies the creator when present.

        Returns:
            Success status, notification ID, audience, and resolved recipient count.

        Raises:
            AppError: With status 400 for invalid or empty audiences, inactive
                recipients, unsupported tone/category, or absent title/message.

        Notes:
            Resolves recipients before writing and records an audit event when
            an audit service is configured. Authorization is the caller's concern.
        """
        audience = str(payload.get("audience") or "").strip().lower()
        requested = [self._username(item) for item in payload.get("recipients", [])]
        requested = list(dict.fromkeys(item for item in requested if item))
        requested_roles = list(
            dict.fromkeys(self._username(item) for item in payload.get("role_ids", []) if item)
        )
        if audience not in {"all", "roles", "selected"}:
            raise api_error(400, "Broadcast audience must be 'all', 'roles', or 'selected'")

        active_users = self.user_repository.list_active_users_for_notifications()
        active_usernames = {self._username(item.get("username")) for item in active_users}
        active_usernames.discard("")
        if audience == "roles":
            if not requested_roles:
                raise api_error(400, "At least one role is required for a role broadcast")
            role_recipients = {
                self._username(item.get("username"))
                for item in self.user_repository.list_active_users_for_notifications(
                    role_ids=requested_roles
                )
            }
            role_recipients.discard("")
            recipients = sorted(role_recipients)
        else:
            recipients = sorted(active_usernames if audience == "all" else set(requested))
        invalid = sorted(set(recipients) - active_usernames)
        if invalid:
            raise api_error(
                400, f"Unknown or inactive notification recipient(s): {', '.join(invalid)}"
            )
        if not recipients:
            raise api_error(400, "The broadcast has no active recipients")

        notification_id = self.create_notification(
            audience="users",
            recipients=recipients,
            tone=str(payload.get("tone") or "info"),
            category=str(payload.get("category") or "application"),
            title=str(payload.get("title") or "").strip(),
            message=str(payload.get("message") or "").strip(),
            source="Administrative broadcast",
            created_by=getattr(actor, "username", None) or "system",
            email_recipients=recipients if self.email_sender else [],
            is_broadcast=True,
            severity=payload.get("severity") or "info",
            expires_at=payload.get("expires_at"),
        )
        if self.audit_service:
            self.audit_service.record(
                "notification.broadcast.created",
                f"Notification broadcast '{payload.get('title')}' created",
                category="administration",
                actor=actor,
                resource_type="notification",
                resource_id=notification_id,
                resource_name=str(payload.get("title") or ""),
                tags=("notification", "broadcast"),
                metadata={
                    "audience": audience,
                    "role_ids": requested_roles,
                    "recipient_count": len(recipients),
                },
            )
        return {
            "status": "ok",
            "notification_id": notification_id,
            "audience": audience,
            "recipient_count": len(recipients),
            "email_state": "pending" if self.email_sender else "not_configured",
        }

    def deliver_emails(self, *, limit: int = 10) -> dict[str, Any]:
        """Deliver a bounded batch of persisted broadcast emails.

        Args:
            limit: Maximum recipients per worker invocation, bounded to 1 through 50.

        Returns:
            Delivery counts, or not_configured when SMTP was not supplied.

        Notes:
            Rechecks account activation and address at send time. Email contains an inbox
            link, not clinical details or the notification body. Failed sends are retained
            as failed; only abandoned worker leases can be retried automatically.
        """
        if self.email_sender is None:
            return {"status": "not_configured", "sent": 0}
        counts = {"sent": 0, "failed": 0, "skipped": 0, "unknown": 0}
        for _ in range(max(1, min(limit, 50))):
            claimed = self.notification_repository.claim_email()
            if claimed is None:
                break
            notification, delivery = claimed
            if delivery["attempts"] > 3:
                self.notification_repository.finish_email(
                    notification["_id"],
                    delivery["lease_id"],
                    state="unknown",
                )
                counts["unknown"] += 1
                continue
            user = self.user_repository.user_with_id(delivery["username"])
            address = str((user or {}).get("email") or "").strip()
            state = "skipped"
            if user and user.get("is_active", True) and address:
                sent = self.email_sender(
                    to_email=address,
                    subject="Coyote3 administrative notification",
                    text_body=(
                        "A new administrative message is available in your Coyote3 inbox.\n\n"
                        f"Open notifications: {self.inbox_url}\n\n"
                        "Sign in to read the message. This email contains no clinical information."
                    ),
                    purpose="broadcast",
                    severity=notification.get("severity") or "info",
                    action_url=self.inbox_url,
                    action_label="Open notifications",
                )
                state = "sent" if sent else "failed"
            self.notification_repository.finish_email(
                notification["_id"],
                delivery["lease_id"],
                state=state,
            )
            counts[state] += 1
        return {"status": "ok", **counts}

    def notify_password_reset_request(self, *, account_username: str) -> str | None:
        """Notify active administrators about a valid self-service reset request."""
        admin_users = self.user_repository.list_active_users_for_notifications(
            role_ids=["sys_admin", "superuser"]
        )
        recipients = sorted(
            {
                self._username(item.get("username"))
                for item in admin_users
                if self._username(item.get("username"))
            }
        )
        if not recipients:
            return None
        notification_id = self.create_notification(
            audience="users",
            recipients=recipients,
            tone="warning",
            category="security",
            title="Password reset requested",
            message=f"A self-service password reset was requested for account {account_username}.",
            source="Authentication",
            resource={"type": "user", "id": account_username, "name": account_username},
            created_by="system",
        )
        if self.audit_service:
            self.audit_service.record(
                "authentication.password_reset.requested",
                f"Password reset requested for account '{account_username}'",
                severity="warning",
                category="security",
                actor="anonymous",
                resource_type="user",
                resource_id=account_username,
                resource_name=account_username,
                tags=("authentication", "password_reset"),
            )
        return notification_id

    def create_notification(
        self,
        *,
        audience: str,
        recipients: list[str],
        tone: str,
        category: str,
        title: str,
        message: str,
        source: str,
        created_by: str,
        resource: dict[str, Any] | None = None,
        email_recipients: list[str] | None = None,
        is_broadcast: bool = False,
        severity: str = "info",
        expires_at: datetime | None = None,
    ) -> str:
        """Persist a notification with expiry and initially empty recipient states.

        Args:
            audience: Audience marker stored unchanged.
            recipients: Recipient logins stored unchanged; callers resolve membership.
            tone: Configured notification tone, stripped and lowercased.
            category: Configured notification category, stripped and lowercased.
            title: Required title, truncated to 160 characters.
            message: Required body, truncated to 5000 characters.
            source: Origin label, truncated to 160 characters.
            created_by: Creator login; blank values become system.
            resource: Optional resource reference; empty mappings are stored as None.
            email_recipients: Resolved recipient usernames for an atomic broadcast outbox.
            is_broadcast: Whether only the sender may withdraw the message.
            severity: Semantic message importance shown independently of category.
            expires_at: Optional UTC-aware broadcast visibility deadline; None means no expiry.

        Returns:
            Identifier returned by the notification repository.

        Raises:
            AppError: With status 400 for unsupported tone/category or empty title/body.
        """
        normalized_tone = tone.strip().lower()
        normalized_category = category.strip().lower()
        if normalized_tone not in NOTIFICATIONS.tones:
            raise api_error(400, f"Unsupported notification tone: {tone}")
        if normalized_category not in NOTIFICATIONS.categories:
            raise api_error(400, f"Unsupported notification category: {category}")
        if not title or not message:
            raise api_error(400, "Notification title and message are required")
        now = datetime.now(timezone.utc)
        if severity not in {"info", "important", "warning", "critical", "success"}:
            raise api_error(400, "Unsupported notification severity")
        if expires_at is not None and (expires_at.tzinfo is None or expires_at <= now):
            raise api_error(400, "Expiry must be a future timezone-aware date")
        return self.notification_repository.create(
            {
                "audience": audience,
                "recipients": recipients,
                "tone": normalized_tone,
                "category": normalized_category,
                "title": title[:160],
                "message": message[:5000],
                "source": source[:160],
                "resource": resource or None,
                "created_by": self._username(created_by) or "system",
                "created_on": now,
                "updated_on": now,
                "expires_on": expires_at
                if is_broadcast
                else now + timedelta(days=self.retention_days),
                "is_broadcast": is_broadcast,
                "severity": severity,
                "read_by": [],
                "dismissed_by": [],
                "email_deliveries": [
                    {"username": username, "state": "pending", "attempts": 0}
                    for username in dict.fromkeys(email_recipients or [])
                ],
            }
        )

    @staticmethod
    def _username(value: Any) -> str:
        """Canonicalize a login or role identifier.

        Args:
            value: Identifier to stringify; falsey values become an empty string.

        Returns:
            Stripped, lowercase text.
        """
        return str(value or "").strip().lower()

    @staticmethod
    def _display_name(user: dict[str, Any]) -> str:
        """Choose a full name, joined first/last names, or login for display.

        Args:
            user: User document with optional name fields.

        Returns:
            First nonempty name representation, or an empty string without a login.
        """
        return (
            str(user.get("fullname") or "").strip()
            or " ".join(
                part
                for part in (
                    str(user.get("firstname") or "").strip(),
                    str(user.get("lastname") or "").strip(),
                )
                if part
            )
            or str(user.get("username") or "")
        )

    @staticmethod
    def _serialize(document: dict[str, Any], *, username: str) -> dict[str, Any]:
        """Expose notification text and the requesting recipient's read state.

        Args:
            document: Stored notification with optional presentation fields.
            username: Canonical recipient login checked against read_by.

        Returns:
            Inbox row with a string identifier and ISO timestamp when supported.
        """
        created_on = document.get("created_on")
        return {
            "id": str(document.get("_id") or ""),
            "tone": document.get("tone") or "info",
            "category": document.get("category") or "application",
            "title": document.get("title") or "Notification",
            "message": document.get("message") or "",
            "source": document.get("source") or "",
            "resource": document.get("resource"),
            "created_at": NotificationService._timestamp(created_on) or "",
            "created_by": document.get("created_by") or "system",
            "read": username in set(document.get("read_by") or []),
            "is_broadcast": bool(document.get("is_broadcast")),
            "severity": document.get("severity")
            or {"error": "critical", "warning": "warning", "success": "success"}.get(
                document.get("tone"), "info"
            ),
            "can_clear": not document.get("is_broadcast") or document.get("created_by") == username,
            "expires_at": NotificationService._timestamp(document.get("expires_on")),
            "withdrawn_at": NotificationService._timestamp(document.get("withdrawn_on")),
        }

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        """Serialize MongoDB UTC timestamps with an explicit browser-readable offset.

        Args:
            value: Stored datetime; MongoDB's timezone-naive values represent UTC.

        Returns:
            ISO timestamp with an offset, or None when no timestamp is stored.
        """
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
