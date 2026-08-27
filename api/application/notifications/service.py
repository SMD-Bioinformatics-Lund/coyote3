"""Recipient-scoped notification workflows."""

from __future__ import annotations

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
    ) -> "NotificationService":
        return cls(
            notification_repository=store.notification_repository,
            user_repository=store.user_repository,
            retention_days=retention_days,
            audit_service=audit_service,
        )

    def __init__(
        self,
        *,
        notification_repository: Any,
        user_repository: Any,
        retention_days: int,
        audit_service: Any | None = None,
    ) -> None:
        self.notification_repository = notification_repository
        self.user_repository = user_repository
        self.retention_days = max(7, int(retention_days or 180))
        self.audit_service = audit_service

    def inbox(self, *, username: str, limit: int = 200) -> dict[str, Any]:
        normalized = self._username(username)
        rows = self.notification_repository.list_for_user(normalized, limit=limit)
        notifications = [self._serialize(item, username=normalized) for item in rows]
        return {
            "notifications": notifications,
            "unread_count": sum(1 for item in notifications if not item["read"]),
        }

    def mark_read(self, *, notification_id: str, username: str) -> dict[str, Any]:
        changed = self.notification_repository.mark_read(notification_id, self._username(username))
        if not changed:
            raise api_error(404, "Notification not found")
        return {"status": "ok", "changed": 1}

    def mark_all_read(self, *, username: str) -> dict[str, Any]:
        changed = self.notification_repository.mark_all_read(self._username(username))
        return {"status": "ok", "changed": changed}

    def dismiss(self, *, notification_id: str, username: str) -> dict[str, Any]:
        changed = self.notification_repository.dismiss(notification_id, self._username(username))
        if not changed:
            raise api_error(404, "Notification not found")
        return {"status": "ok", "changed": 1}

    def dismiss_all(self, *, username: str) -> dict[str, Any]:
        changed = self.notification_repository.dismiss_all(self._username(username))
        return {"status": "ok", "changed": changed}

    def recipient_options(self) -> dict[str, Any]:
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

    def broadcast(self, *, payload: dict[str, Any], actor: Any) -> dict[str, Any]:
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
            audience="all" if audience == "all" else "users",
            recipients=[] if audience == "all" else recipients,
            tone=str(payload.get("tone") or "info"),
            category=str(payload.get("category") or "application"),
            title=str(payload.get("title") or "").strip(),
            message=str(payload.get("message") or "").strip(),
            source="Administrative broadcast",
            created_by=getattr(actor, "username", None) or "system",
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
        }

    def notify_password_reset_request(self, *, account_username: str) -> str | None:
        """Notify active administrators about a valid self-service reset request."""
        admin_users = self.user_repository.list_active_users_for_notifications(
            role_ids=["admin", "superuser"]
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
    ) -> str:
        normalized_tone = tone.strip().lower()
        normalized_category = category.strip().lower()
        if normalized_tone not in NOTIFICATIONS.tones:
            raise api_error(400, f"Unsupported notification tone: {tone}")
        if normalized_category not in NOTIFICATIONS.categories:
            raise api_error(400, f"Unsupported notification category: {category}")
        if not title or not message:
            raise api_error(400, "Notification title and message are required")
        now = datetime.now(timezone.utc)
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
                "expires_on": now + timedelta(days=self.retention_days),
                "read_by": [],
                "dismissed_by": [],
            }
        )

    @staticmethod
    def _username(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _display_name(user: dict[str, Any]) -> str:
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
        created_on = document.get("created_on")
        return {
            "id": str(document.get("_id") or ""),
            "tone": document.get("tone") or "info",
            "category": document.get("category") or "application",
            "title": document.get("title") or "Notification",
            "message": document.get("message") or "",
            "source": document.get("source") or "",
            "resource": document.get("resource"),
            "created_at": created_on.isoformat()
            if hasattr(created_on, "isoformat")
            else str(created_on or ""),
            "created_by": document.get("created_by") or "system",
            "read": username in set(document.get("read_by") or []),
        }
