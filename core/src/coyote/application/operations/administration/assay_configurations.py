# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized assay configurations operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote.application.resources.aspc import AspcService


class AssayConfigurations:
    """Authorized assay configurations operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], AspcService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def versions(self, *, identifier: str) -> list[dict[str, Any]]:
        """Read all retained configuration revisions; requires assay.config:view.

        Args:
            identifier: Stable configuration identifier, including retired-only scopes.

        Returns:
            Current and retired versions ordered newest first.

        Raises:
            AppError: Authentication or assay.config:view permission is missing.
        """
        return self._runtime.execute(
            "assay_configurations.versions",
            ("assay.config:view",),
            lambda actor, sample: self._service().versions(identifier),
        )

    def list_aspc(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the assay-config list.

        Args:
            q: Case-insensitive text search across configuration identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.list_aspc",
            ("assay.config:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_aspc_context(self, *, category: str = "DNA") -> dict[str, Any]:
        """Return create-form context for an assay config.

        Args:
            category: Requested assay category.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.create_aspc_context",
            ("assay.config:create",),
            lambda actor, sample: self._service().create_context_payload(
                category=category, actor_username=actor.username
            ),
        )

    def aspc_context(self, *, assay_id: str) -> dict[str, Any]:
        """Return edit-form context for an assay config.

        Args:
            assay_id: Assay-config identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.config:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.aspc_context",
            ("assay.config:view",),
            lambda actor, sample: self._service().context_payload(assay_id=assay_id),
        )

    def create_aspc(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an assay config.

        Args:
            payload: Submitted assay-config payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.create_aspc",
            ("assay.config:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def update_aspc(self, *, assay_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an assay config.

        Args:
            assay_id: Assay-config identifier to update.
            payload: Submitted assay-config payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.update_aspc",
            ("assay.config:edit",),
            lambda actor, sample: self._service().update(
                assay_id=assay_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("aspc", assay_id),
        )

    def toggle_aspc(self, *, assay_id: str) -> dict[str, Any]:
        """Toggle assay-config active status.

        Args:
            assay_id: Assay-config identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.toggle_aspc",
            ("assay.config:edit",),
            lambda actor, sample: self._service().toggle(assay_id=assay_id),
            edit_resource=("aspc", assay_id),
            editing_session_required=False,
        )

    def delete_aspc(self, *, assay_id: str) -> dict[str, Any]:
        """Delete an assay config.

        Args:
            assay_id: Assay-config identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.delete_aspc",
            ("assay.config:delete",),
            lambda actor, sample: self._service().delete(assay_id=assay_id),
            edit_resource=("aspc", assay_id),
            editing_session_required=False,
        )

    def validate_aspc_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an aspc_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "assay_configurations.validate_aspc_id",
                ("assay.config:create",),
                lambda actor, sample: self._service().assay_config_exists(
                    aspc_id=str(payload.get("aspc_id", "") or ""),
                    asp_id=str(payload.get("asp_id", "") or ""),
                    diagnosis_id=str(payload.get("diagnosis_id", "") or ""),
                    environment=str(payload.get("environment", "") or ""),
                ),
            )
        )
