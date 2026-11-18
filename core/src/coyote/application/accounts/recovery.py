# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Provider-specific recovery without handling directory credentials."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from coyote.config.constants import DEFAULT_AUTH_PROVIDER, normalize_auth_types
from coyote.contracts.auth import PasswordRecoveryRecord
from coyote.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote.application.audit.service import AuditService
    from coyote.application.notifications.service import NotificationService


class RecoveryRepository(Protocol):
    """Identity-store operations required by assisted recovery."""

    def user_by_username(self, username: str) -> dict[str, Any] | None:
        """Return an account by canonical username."""
        ...

    def request_recovery(self, username: str, record: dict[str, Any]) -> dict[str, Any] | None:
        """Atomically open a request or return the existing pending request."""
        ...

    def recovery_requests(self) -> list[dict[str, Any]]:
        """Return pending requests without credential fields."""
        ...

    def complete_recovery(self, request_id: str, actor: str) -> dict[str, Any] | None:
        """Complete once, retaining actor/time; return the record for safe retries."""
        ...


class AccountRecoveryService:
    """Dispatch local recovery and track externally performed resets."""

    def __init__(
        self,
        repository: RecoveryRepository,
        notifications: "NotificationService",
        issue_token: Callable[..., dict[str, Any]],
        audit: "AuditService",
    ) -> None:
        """Bind identity persistence, durable notifications, local delivery and audit."""
        self.repository = repository
        self.notifications = notifications
        self.issue_token = issue_token
        self.audit = audit

    def request(
        self,
        *,
        login_identifier: str,
        purpose: str = "reset",
        actor_username: str | None = None,
        provider: str = "auto",
    ) -> dict[str, str]:
        """Accept a username with a neutral result for missing or inactive accounts.

        Local accounts with email receive the existing one-time link. LDAP and
        local accounts without email create an administrator-assisted request.
        Auto selects local when an account supports both providers.
        """
        if purpose != "reset" or provider not in {"auto", "local", "ldap"}:
            raise ValueError("Unsupported recovery operation")
        username = login_identifier.strip().lower()
        user = self.repository.user_by_username(username)
        if not user or not user.get("is_active", True):
            return {"status": "ok"}
        providers = normalize_auth_types(user.get("auth_type") or [DEFAULT_AUTH_PROVIDER])
        selected = ("local" if "local" in providers else "ldap") if provider == "auto" else provider
        if selected not in providers:
            return {"status": "ok"}
        if selected == "local" and str(user.get("email") or "").strip():
            self.issue_token(login_identifier=username, purpose="reset", actor_username=None)
            return {"status": "ok"}
        record = PasswordRecoveryRecord(
            request_id=str(uuid4()),
            username=username,
            provider=selected,
            requested_at=datetime.now(timezone.utc),
        )
        self.audit.record(
            "authentication.password_recovery.requested",
            "Assisted recovery requested",
            actor="anonymous",
            category="security",
            resource_type="user",
            resource_id=username,
            provider=selected,
        )
        persisted = self.repository.request_recovery(username, record.model_dump(mode="python"))
        if persisted:
            self._notify(PasswordRecoveryRecord.model_validate(persisted), completed=False)
        return {"status": "ok"}

    def pending(self) -> list[PasswordRecoveryRecord]:
        """Return open requests for an authorized account administrator."""
        return [
            PasswordRecoveryRecord.model_validate(row)
            for row in self.repository.recovery_requests()
        ]

    def complete(self, request_id: str, actor: str) -> PasswordRecoveryRecord:
        """Record an administrator's confirmation after an external recovery.

        This operation never sets a password. A retry retains the original actor
        and completion time and retries the same durable notification identity.
        """
        self.audit.record(
            "authentication.password_recovery.completion_requested",
            "Administrator confirmed recovery was performed outside this workflow",
            actor=actor,
            category="security",
            resource_type="password_recovery",
            resource_id=request_id,
        )
        stored = self.repository.complete_recovery(request_id, actor)
        if not stored:
            raise api_error(409, "Recovery request is unavailable or the account has changed")
        record = PasswordRecoveryRecord.model_validate(stored)
        self.audit.record(
            "authentication.password_recovery.completed",
            "Assisted recovery confirmed completed",
            actor=record.completed_by,
            category="security",
            resource_type="user",
            resource_id=record.username,
            provider=record.provider,
            metadata={
                "request_id": record.request_id,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            },
        )
        self._notify(record, completed=True)
        return record

    def _notify(self, record: PasswordRecoveryRecord, *, completed: bool) -> None:
        """Persist deduplicated inbox messages and email-outbox deliveries."""
        if completed:
            recipients = [record.username]
            title = "Password recovery completed"
            message = (
                f"An administrator confirmed that your {record.provider} account recovery "
                "has been completed. Sign in using the instructions provided by your administrator."
            )
        else:
            admins = self.notifications.user_repository.list_active_users_for_notifications(
                role_ids=["sys_admin", "superuser"]
            )
            recipients = sorted({row["username"] for row in admins if row.get("username")})
            title = "Password recovery requires assistance"
            instruction = (
                "Reset the password through the external LDAP service."
                if record.provider == "ldap"
                else "Verify the account owner, associate a verified email in account administration, and send a reset link."
            )
            message = f"Account {record.username} requested recovery. {instruction} Then mark the request completed in Users. Never include passwords in Coyote notifications."
        self.notifications.create_notification(
            audience="users",
            recipients=recipients,
            email_recipients=recipients,
            tone="info" if completed else "warning",
            category="security",
            title=title,
            message=message,
            source="Account recovery",
            severity="important",
            created_by=record.completed_by or "system",
            resource={"type": "user", "id": record.username, "name": record.username},
            event_id=f"password-recovery:{record.request_id}:{'completed' if completed else 'requested'}",
        )
