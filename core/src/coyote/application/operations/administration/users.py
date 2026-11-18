# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized users operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.config.factory_defaults import factory_value
from coyote.contracts.auth import PasswordRecoveryRecord, SessionActivitySummary
from coyote.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote.application.accounts.recovery import AccountRecoveryService
    from coyote.application.accounts.sessions import SessionActivityRepository
    from coyote.application.accounts.users import UserManagementService


class Users:
    """Authorized users operations shared by HTTP and local callers."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], UserManagementService],
        sessions: Callable[[], SessionActivityRepository],
        recovery: Callable[[], AccountRecoveryService],
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
            recovery: Assisted recovery workflow.
            sessions: Read-only aggregate login-session persistence.
        """
        self._runtime, self._service = runtime, service
        self._sessions = sessions
        self._recovery = recovery

    def recovery_requests(self) -> list[PasswordRecoveryRecord]:
        """List assisted recovery requests for system administrators."""

        def read(actor: Any, sample: dict[str, Any] | None) -> list[PasswordRecoveryRecord]:
            self._require_recovery_admin(actor)
            return self._recovery().pending()

        return self._runtime.execute("users.recovery_requests", ("user:edit",), read)

    def complete_recovery(self, request_id: str) -> PasswordRecoveryRecord:
        """Confirm externally completed recovery, preserving the original actor on retry."""

        def complete(actor: Any, sample: dict[str, Any] | None) -> PasswordRecoveryRecord:
            self._require_recovery_admin(actor)
            return self._recovery().complete(request_id, actor.username)

        return self._runtime.execute("users.complete_recovery", ("user:edit",), complete)

    @staticmethod
    def _require_recovery_admin(actor: Any) -> None:
        """Limit recovery handling to system administrators and superusers."""
        if not actor.is_superuser and "sys_admin" not in actor.roles:
            raise api_error(403, "Account recovery requires a system administrator")

    def session_activity(self) -> SessionActivitySummary:
        """Return current login counts for a verified superuser.

        Returns:
            Distinct signed-in users, valid sessions and recent request activity.

        Raises:
            AppError: The session is invalid or the current actor is not a superuser.
        """

        return self._runtime.execute(
            "users.session_activity",
            ("user:list",),
            lambda actor, sample: self._sessions().activity_summary(
                recent_activity_seconds=factory_value("accounts.sessions.recent_activity_seconds")
            ),
            superuser_only=True,
        )

    def list_users(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the user list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (user:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.list_users",
            ("user:list",),
            lambda actor, sample: self._service().list_users_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_user_context(self) -> dict[str, Any]:
        """Return create-form context for a user.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.create_user_context",
            ("user:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def user_context(self, *, user_id: str) -> dict[str, Any]:
        """Return edit-form context for a user.

        Args:
            user_id: Registered account identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (user:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.user_context",
            ("user:view",),
            lambda actor, sample: self._service().context_payload(user_id=user_id),
        )

    def create_user(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a user.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        permissions: tuple[str, ...] = ("user:create",)
        form = payload.get("form_data") or {}
        if isinstance(form, dict):
            if "roles" in form:
                permissions += ("user:role:edit",)
            if {"asp_ids", "asp_groups", "environments"} & form.keys():
                permissions += ("user:group:edit",)
        return self._runtime.execute(
            "users.create_user",
            permissions,
            lambda actor, sample: self._service().create_user(
                payload=payload,
                actor_username=actor.username,
                actor_is_superuser=actor.is_superuser,
            ),
        )

    def update_user(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a user.

        Args:
            user_id: Registered account identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        permissions: tuple[str, ...] = ("user:edit",)
        form = payload.get("form_data") or {}
        if isinstance(form, dict):
            if "roles" in form:
                permissions += ("user:role:edit",)
            if {"asp_ids", "asp_groups", "environments"} & form.keys():
                permissions += ("user:group:edit",)
        return self._runtime.execute(
            "users.update_user",
            permissions,
            lambda actor, sample: self._service().update_user(
                user_id=user_id,
                payload=payload,
                actor_username=actor.username,
                actor_is_superuser=actor.is_superuser,
            ),
            edit_resource=("users", user_id),
        )

    def delete_user(self, *, user_id: str) -> dict[str, Any]:
        """Delete a user.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.delete_user",
            ("user:delete",),
            lambda actor, sample: self._service().delete_user(
                user_id=user_id, actor_is_superuser=actor.is_superuser
            ),
            edit_resource=("users", user_id),
            editing_session_required=False,
        )

    def toggle_user_status(self, *, user_id: str) -> dict[str, Any]:
        """Toggle a user's active status.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.toggle_user_status",
            ("user:edit",),
            lambda actor, sample: self._service().toggle_user(
                user_id=user_id, actor_is_superuser=actor.is_superuser
            ),
            edit_resource=("users", user_id),
            editing_session_required=False,
        )

    def invite_local_user(self, *, user_id: str) -> dict[str, Any]:
        """Issue a set-password invite link for local users.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.invite_local_user",
            ("user:edit",),
            lambda actor, sample: self._service().send_local_user_invite(
                user_id=user_id, actor_username=actor.username
            ),
        )

    def validate_username(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a username is already in use.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "users.validate_username",
                ("user:create",),
                lambda actor, sample: self._service().username_exists(
                    username=str(payload.get("username", ""))
                ),
            )
        )

    def validate_email(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an email address is already in use.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "users.validate_email",
                ("user:create",),
                lambda actor, sample: self._service().email_exists(
                    email=str(payload.get("email", ""))
                ),
            )
        )
