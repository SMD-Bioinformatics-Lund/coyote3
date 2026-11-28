# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized catalog authoring operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.public import PublicAssayCatalogImportRequest as DraftImport
from coyote.contracts.public import PublicAssayCatalogTransitionRequest as Transition
from coyote.contracts.public import PublicAssayCatalogUpdateRequest as DraftUpdate

if TYPE_CHECKING:
    from coyote.application.resources.public_assay_catalog import (
        PublicAssayCatalogManagementService,
    )


class CatalogAuthoring:
    """Authorized catalog authoring operations shared by HTTP and local callers."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], PublicAssayCatalogManagementService],
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def delete_version(self, *, identifier: str, revision: int) -> dict[str, Any]:
        """Delete an unchanged unpublished version; requires catalog:draft.

        Args:
            identifier: Catalog version to delete.
            revision: Expected saved revision; concurrent changes are rejected.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.delete_version",
            ("catalog:draft",),
            lambda actor, sample: self._service().delete_unpublished(
                identifier, revision, actor=actor.username
            ),
            edit_resource=("assay-catalog", identifier),
            editing_session_required=False,
        )

    def workspace(self) -> dict[str, Any]:
        """Read the catalog authoring workspace; requires `catalog:view`.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.workspace",
            ("catalog:view",),
            lambda actor, sample: self._service().workspace(),
        )

    def version(self, *, oid: str) -> dict[str, Any]:
        """Read one catalog version; requires `catalog:view`.

        Args:
            oid: Catalog version document identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.version",
            ("catalog:view",),
            lambda actor, sample: self._service().document(oid),
        )

    def revisions(self, *, oid: str) -> dict[str, Any]:
        """Read a catalog version's revision history; requires `catalog:view`.

        Args:
            oid: Catalog version document identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.revisions",
            ("catalog:view",),
            lambda actor, sample: self._service().revisions(oid),
        )

    def preview_offerings(self, *, payload: DraftImport) -> dict[str, Any]:
        """Preview public services from validated sources without publishing; requires catalog:view.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview_offerings",
            ("catalog:view",),
            lambda actor, sample: self._service().preview_offerings(
                payload.document, actor=actor.username
            ),
        )

    def preview(
        self,
        *,
        payload: DraftImport,
        mod: str | None = None,
        cat: str | None = None,
        isgl_key: str | None = None,
    ) -> dict[str, Any]:
        """Render supplied catalog content without saving it; requires `catalog:view`.

        Args:
            payload: Catalog document to validate and render.
            mod: Optional modality selection; None leaves it unselected.
            cat: Optional category selection within the modality.
            isgl_key: Optional gene-list selection for the category.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview",
            ("catalog:view",),
            lambda actor, sample: self._service().preview(
                payload.document, actor=actor.username, mod=mod, cat=cat, isgl_key=isgl_key
            ),
        )

    def preview_matrix(
        self, *, payload: DraftImport, page: int = 1, per_page: int = 100, gene: str | None = None
    ) -> dict[str, Any]:
        """Preview a catalog's gene matrix without saving it; requires `catalog:view`.

        Args:
            payload: Catalog document to validate and render.
            page: One-based matrix page; defaults to 1.
            per_page: Rows per page from 1 to 500; defaults to 100.
            gene: Optional gene search text; None omits gene filtering.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview_matrix",
            ("catalog:view",),
            lambda actor, sample: self._service().preview_matrix(
                payload.document, actor=actor.username, page=page, per_page=per_page, gene=gene
            ),
        )

    def create(self) -> dict[str, Any]:
        """Create a catalog draft from current content; requires `catalog:draft`.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.create",
            ("catalog:draft",),
            lambda actor, sample: self._service().create(actor=actor.username),
        )

    def import_draft(self, *, payload: DraftImport) -> dict[str, Any]:
        """Import catalog content as a new draft; requires `catalog:draft`.

        Args:
            payload: Full catalog document or supported modality export envelope.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.import_draft",
            ("catalog:draft",),
            lambda actor, sample: self._service().create(
                actor=actor.username, imported=payload.document
            ),
        )

    def update(self, *, oid: str, payload: DraftUpdate) -> dict[str, Any]:
        """Replace draft catalog content at a revision; requires `catalog:draft`.

        Args:
            oid: Draft version document identifier.
            payload: Expected revision and replacement catalog content.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.update",
            ("catalog:draft",),
            lambda actor, sample: self._service().update(
                oid, payload.revision, payload.catalog, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
        )

    def submit(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Submit a catalog draft to an independent reviewer; requires `catalog:submit`.

        Args:
            oid: Draft version document identifier.
            payload: Expected revision and reviewer username in assignee.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:submit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.submit",
            ("catalog:submit",),
            lambda actor, sample: self._service().submit(
                oid, payload.revision, payload.assignee, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )

    def review(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Approve or reject an assigned catalog review; requires `catalog:review`.

        Args:
            oid: Submitted catalog version document identifier.
            payload: Expected revision, approval flag, reason, and publisher assignee.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:review), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.review",
            ("catalog:review",),
            lambda actor, sample: self._service().decide(
                oid,
                payload.revision,
                actor=actor.username,
                approve=payload.approve,
                publisher=payload.assignee,
                reason=payload.reason,
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )

    def publish(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Publish an approved catalog version; requires `catalog:publish`.

        Args:
            oid: Approved catalog version document identifier.
            payload: Expected revision; other transition fields are not used here.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:publish), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.publish",
            ("catalog:publish",),
            lambda actor, sample: self._service().publish(
                oid, payload.revision, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )
