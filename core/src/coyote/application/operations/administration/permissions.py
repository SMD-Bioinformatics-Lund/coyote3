# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized permissions operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote.application.accounts.permissions import PermissionManagementService


class Permissions:
    """Authorized permissions operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], PermissionManagementService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_permission(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a permission policy.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.create_permission",
            ("permission.policy:create",),
            lambda actor, sample: self._service().create_permission(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_permissions(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the permission-policy list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.list_permissions",
            ("permission.policy:list",),
            lambda actor, sample: self._service().list_permissions_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_permission_context(self) -> dict[str, Any]:
        """Return create-form context for a permission policy.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.create_permission_context",
            ("permission.policy:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def permission_context(self, *, perm_id: str) -> dict[str, Any]:
        """Return edit-form context for a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (permission.policy:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.permission_context",
            ("permission.policy:view",),
            lambda actor, sample: self._service().context_payload(permission_id=perm_id),
        )

    def update_permission(self, *, perm_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.update_permission",
            ("permission.policy:edit",),
            lambda actor, sample: self._service().update_permission(
                permission_id=perm_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("permissions", perm_id),
        )

    def toggle_permission_status(self, *, perm_id: str) -> dict[str, Any]:
        """Toggle a permission policy's active status.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.toggle_permission_status",
            ("permission.policy:edit",),
            lambda actor, sample: self._service().toggle_permission(permission_id=perm_id),
            edit_resource=("permissions", perm_id),
            editing_session_required=False,
        )

    def delete_permission(self, *, perm_id: str) -> dict[str, Any]:
        """Delete a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.delete_permission",
            ("permission.policy:delete",),
            lambda actor, sample: self._service().delete_permission(permission_id=perm_id),
            edit_resource=("permissions", perm_id),
            editing_session_required=False,
        )

    def validate_permission_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a permission_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "permissions.validate_permission_id",
                ("permission.policy:create",),
                lambda actor, sample: self._service().permission_exists(
                    permission_id=str(payload.get("permission_id", ""))
                ),
            )
        )
