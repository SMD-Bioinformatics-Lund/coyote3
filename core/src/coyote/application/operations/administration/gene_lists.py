# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized gene lists operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote.application.resources.isgl import IsglService


class GeneLists:
    """Authorized gene lists operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], IsglService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def versions(self, *, identifier: str) -> list[dict[str, Any]]:
        """Read all retained gene-list revisions; requires gene_list.insilico:view.

        Args:
            identifier: Stable gene-list identifier, including retired-only lists.

        Returns:
            Current and retired versions ordered newest first.

        Raises:
            AppError: Authentication or gene_list.insilico:view permission is missing.
        """
        return self._runtime.execute(
            "gene_lists.versions",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().versions(identifier),
        )

    def create_genelist(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a genelist.

        Args:
            payload: Submitted genelist payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.create_genelist",
            ("gene_list.insilico:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_genelists(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the genelist list.

        Args:
            q: Case-insensitive text search across genelist identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.list_genelists",
            ("gene_list.insilico:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_genelist_context(self) -> dict[str, Any]:
        """Return create-form context for a genelist.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.create_genelist_context",
            ("gene_list.insilico:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def genelist_context(self, *, genelist_id: str) -> dict[str, Any]:
        """Return edit-form context for a genelist.

        Args:
            genelist_id: Genelist identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.genelist_context",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().context_payload(genelist_id=genelist_id),
        )

    def genelist_view_context(
        self, *, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any]:
        """Return read-only context for a genelist.

        Args:
            genelist_id: Genelist identifier to load.
            assay: Optional assay used to filter visible genes.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.genelist_view_context",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().view_context_payload(
                genelist_id=genelist_id, assay=assay
            ),
        )

    def update_genelist(self, *, genelist_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a genelist.

        Args:
            genelist_id: Genelist identifier to update.
            payload: Submitted genelist payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.update_genelist",
            ("gene_list.insilico:edit",),
            lambda actor, sample: self._service().update(
                genelist_id=genelist_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("genelists", genelist_id),
        )

    def toggle_genelist(self, *, genelist_id: str) -> dict[str, Any]:
        """Toggle genelist active status.

        Args:
            genelist_id: Genelist identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.toggle_genelist",
            ("gene_list.insilico:edit",),
            lambda actor, sample: self._service().toggle(genelist_id=genelist_id),
            edit_resource=("genelists", genelist_id),
            editing_session_required=False,
        )

    def delete_genelist(self, *, genelist_id: str) -> dict[str, Any]:
        """Delete a genelist.

        Args:
            genelist_id: Genelist identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.delete_genelist",
            ("gene_list.insilico:delete",),
            lambda actor, sample: self._service().delete(genelist_id=genelist_id),
            edit_resource=("genelists", genelist_id),
            editing_session_required=False,
        )

    def validate_isgl_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an isgl_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "gene_lists.validate_isgl_id",
                ("gene_list.insilico:create",),
                lambda actor, sample: self._service().genelist_exists(
                    isgl_id=str(payload.get("isgl_id", ""))
                ),
            )
        )
