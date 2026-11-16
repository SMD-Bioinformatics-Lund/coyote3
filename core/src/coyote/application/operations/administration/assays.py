# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized assays operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote.application.resources.asp import AspService


class Assays:
    """Authorized assays operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], AspService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def versions(self, *, identifier: str) -> list[dict[str, Any]]:
        """Read all retained assay revisions; requires assay.panel:view.

        Args:
            identifier: Stable assay identifier, including a retired-only assay.

        Returns:
            Current and retired versions ordered newest first.

        Raises:
            AppError: Authentication or assay.panel:view permission is missing.
        """
        return self._runtime.execute(
            "assays.versions",
            ("assay.panel:view",),
            lambda actor, sample: self._service().versions(identifier),
        )

    def create_asp(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an assay panel.

        Args:
            payload: Submitted assay-panel payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.create_asp",
            ("assay.panel:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_asp(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the assay-panel list.

        Args:
            q: Case-insensitive text search across panel identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.list_asp",
            ("assay.panel:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_asp_context(self) -> dict[str, Any]:
        """Return create-form context for an assay panel.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.create_asp_context",
            ("assay.panel:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def asp_context(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Return edit-form context for an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.asp_context",
            ("assay.panel:view",),
            lambda actor, sample: self._service().context_payload(panel_id=assay_panel_id),
        )

    def update_asp(self, *, assay_panel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to update.
            payload: Submitted assay-panel payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.update_asp",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().update(
                panel_id=assay_panel_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("asp", assay_panel_id),
        )

    def toggle_asp(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Toggle assay-panel active status.

        Args:
            assay_panel_id: Assay-panel identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.toggle_asp",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().toggle(panel_id=assay_panel_id),
            edit_resource=("asp", assay_panel_id),
            editing_session_required=False,
        )

    def delete_asp(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Delete an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.delete_asp",
            ("assay.panel:delete",),
            lambda actor, sample: self._service().delete(panel_id=assay_panel_id),
            edit_resource=("asp", assay_panel_id),
            editing_session_required=False,
        )

    def validate_asp_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an asp_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "assays.validate_asp_id",
                ("assay.panel:create",),
                lambda actor, sample: self._service().panel_exists(
                    asp_id=str(payload.get("asp_id", ""))
                ),
            )
        )
