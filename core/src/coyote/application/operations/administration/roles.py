# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized roles operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote.application.accounts.roles import RoleManagementService


class Roles:
    """Authorized roles operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], RoleManagementService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_roles(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the role list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (role:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.list_roles",
            ("role:list",),
            lambda actor, sample: self._service().list_roles_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_role_context(self) -> dict[str, Any]:
        """Return create-form context for a role.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.create_role_context",
            ("role:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def role_context(self, *, role_id: str) -> dict[str, Any]:
        """Return edit-form context for a role.

        Args:
            role_id: Registered role identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (role:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.role_context",
            ("role:view",),
            lambda actor, sample: self._service().context_payload(role_id=role_id),
        )

    def create_role(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a role.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.create_role",
            ("role:create",),
            lambda actor, sample: self._service().create_role(
                payload=payload, actor_username=actor.username
            ),
        )

    def update_role(self, *, role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a role.

        Args:
            role_id: Registered role identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.update_role",
            ("role:edit",),
            lambda actor, sample: self._service().update_role(
                role_id=role_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("roles", role_id),
        )

    def toggle_role_status(self, *, role_id: str) -> dict[str, Any]:
        """Toggle a role's active status.

        Args:
            role_id: Registered role identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.toggle_role_status",
            ("role:edit",),
            lambda actor, sample: self._service().toggle_role(role_id=role_id),
            edit_resource=("roles", role_id),
            editing_session_required=False,
        )

    def delete_role(self, *, role_id: str) -> dict[str, Any]:
        """Delete a role.

        Args:
            role_id: Registered role identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.delete_role",
            ("role:delete",),
            lambda actor, sample: self._service().delete_role(role_id=role_id),
            edit_resource=("roles", role_id),
            editing_session_required=False,
        )

    def validate_role_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a role_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "roles.validate_role_id",
                ("role:create",),
                lambda actor, sample: self._service().role_exists(
                    role_id=str(payload.get("role_id", ""))
                ),
            )
        )
