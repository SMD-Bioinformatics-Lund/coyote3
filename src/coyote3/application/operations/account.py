"""Current-account application operations and one-time password recovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error
from coyote3.domain.identity.password_policy import validate_new_password

if TYPE_CHECKING:
    from coyote3.application.accounts.users import UserManagementService
    from coyote3.contracts.auth import ApiPasswordChangeRequest, ApiPasswordResetConfirmRequest


class Account:
    """Edit only the verified current account and its own local password."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], UserManagementService],
        change_password: Callable[..., dict[str, Any]],
    ) -> None:
        """Bind verified identity, account workflows and local credential replacement.

        Args:
            runtime: Trusted current-identity and audit boundary.
            service: Account workflows with injected identity repositories.
            change_password: Verifies the old credential, replaces it and revokes sessions.
        """
        self._runtime, self._service, self._change_password = runtime, service, change_password

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update safe profile fields for the current identity.

        Args:
            payload: Profile fields accepted by the authoritative account validator.

        Returns:
            Updated public profile fields, excluding credential material.

        Raises:
            AppError: Authentication or profile validation fails.
        """
        return self._runtime.execute(
            "account.update_profile",
            None,
            lambda actor, sample: dict(
                self._service().update_own_profile(username=actor.username, payload=payload)
            ),
        )

    def update_ui_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist supported preferences only for the current identity.

        Args:
            payload: Validated preference changes; omitted fields remain unchanged.

        Returns:
            Persisted interface preferences for the current identity.

        Raises:
            AppError: Authentication or preference validation fails.
        """
        return self._runtime.execute(
            "account.update_ui_settings",
            None,
            lambda actor, sample: dict(
                self._service().update_own_ui_settings(username=actor.username, payload=payload)
            ),
        )

    def change_password(self, payload: ApiPasswordChangeRequest) -> dict[str, Any]:
        """Replace the current account's local password and invalidate existing sessions.

        Args:
            payload: Current and proposed passwords; first-login changes require matching
                confirmation. Passwords are never added to application access audit metadata.

        Returns:
            Success acknowledgement and current username.

        Raises:
            AppError: Authentication, confirmation, complexity or current-password checks fail.
        """

        def change(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Validate confirmation and complexity before replacing credential material."""
            if (
                actor.must_change_password or payload.confirm_password is not None
            ) and payload.confirm_password != payload.new_password:
                raise api_error(400, "New password and confirmation must match")
            validate_new_password(payload.new_password)
            result = self._change_password(
                user_id=actor.username,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
            if result.get("status") != "ok":
                raise api_error(400, str(result.get("error") or "Unable to change password"))
            return {"status": "ok", "username": actor.username}

        return self._runtime.execute("account.change_password", None, change)


class PasswordRecovery:
    """One-time credential recovery, with no account enumeration or clinical access."""

    def __init__(
        self, *, request_token: Callable[..., Any], consume_token: Callable[..., dict[str, Any]]
    ) -> None:
        """Bind delivery and atomic one-time verification from the trusted identity adapter.

        Args:
            request_token: Issues and delivers a reset token without disclosing account existence.
            consume_token: Atomically validates, consumes and replaces a credential once.
        """
        self._request_token, self._consume_token = request_token, consume_token

    def request_reset(self, identifier: str) -> dict[str, Any]:
        """Request a recovery link without disclosing whether the account exists.

        Args:
            identifier: User-entered local username or login identifier.

        Returns:
            The same success acknowledgement regardless of account existence.
        """
        self._request_token(login_identifier=identifier, purpose="reset", actor_username=None)
        return {"status": "ok"}

    def confirm_reset(self, payload: ApiPasswordResetConfirmRequest) -> dict[str, Any]:
        """Replace a local password only after a one-time recovery credential is verified.

        Args:
            payload: Expiring single-use token and proposed new password.

        Returns:
            Success acknowledgement after the credential is replaced.

        Raises:
            AppError: Password complexity, token verification or atomic consumption fails.
        """
        validate_new_password(payload.new_password)
        result = self._consume_token(token=payload.token, new_password=payload.new_password)
        if result.get("status") != "ok":
            raise api_error(400, str(result.get("error") or "Password reset failed"))
        return {"status": "ok"}
