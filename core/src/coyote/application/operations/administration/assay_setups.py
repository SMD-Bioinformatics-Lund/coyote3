# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized assay setups operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.schemas.assay_setup import (
    AssaySetupAction,
    AssaySetupContent,
    AssaySetupUpdate,
)

if TYPE_CHECKING:
    from coyote.application.resources.assay_setup import AssaySetupService


class AssaySetups:
    """Authorized assay setups operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], AssaySetupService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def delete_setup(self, *, identifier: str, revision: int) -> dict[str, Any]:
        """Delete an unchanged draft or submitted setup; requires assay.panel:delete.

        Args:
            identifier: Saved setup or catalog-version identifier.
            revision: Expected saved revision; concurrent changes are rejected.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.delete_setup",
            ("assay.panel:delete",),
            lambda actor, sample: self._service().delete_unpublished(
                identifier, revision, actor=actor.username
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def list_setups(self) -> dict[str, Any]:
        """List saved setup summaries; requires assay.panel:list.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.list_setups",
            ("assay.panel:list",),
            lambda actor, sample: self._service().list_payload(),
        )

    def new_setup_context(self) -> dict[str, Any]:
        """Return the assay form and optional scope choices for a new setup.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.new_setup_context",
            ("assay.panel:create",),
            lambda actor, sample: self._service().context(None, actor=actor.username),
        )

    def setup_context(self, *, identifier: str) -> dict[str, Any]:
        """Inspect staged configuration, readiness and revision history without writing data.

        Args:
            identifier: Saved setup or catalog-version identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.setup_context",
            ("assay.panel:view",),
            lambda actor, sample: self._service().context(identifier, actor=actor.username),
        )

    def create_setup(self, *, payload: AssaySetupContent) -> dict[str, Any]:
        """Reserve an assay identifier and save a draft without creating an active ASP.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:create, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.create_setup",
            ("assay.panel:create", "assay.config:create", "gene_list.insilico:create")
            + (("gene_list.insilico:edit",) if payload.existing_gene_list_ids else ()),
            lambda actor, sample: self._service().save(payload, actor=actor.username),
        )

    def save_setup(self, *, identifier: str, payload: AssaySetupUpdate) -> dict[str, Any]:
        """Save the current draft revision; submitted and published setups are immutable.

        Args:
            identifier: Saved setup or catalog-version identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.save_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            )
            + (("gene_list.insilico:edit",) if payload.content.existing_gene_list_ids else ()),
            lambda actor, sample: self._service().save(
                payload.content,
                identifier=identifier,
                revision=payload.revision,
                actor=actor.username,
            ),
            edit_resource=("assay-setups", identifier),
        )

    def submit_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Validate staged resources and assign optional review to an eligible colleague.

        Args:
            identifier: Saved assay setup identifier.
            payload: Expected revision, eligible reviewer in assignee and optional notes.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.submit_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            ),
            lambda actor, sample: self._service().transition(
                identifier,
                payload.revision,
                "submit",
                actor=actor.username,
                reason=payload.reason,
                assignee=payload.assignee,
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def publish_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Publish and atomically activate a complete draft or optionally reviewed setup.

        Args:
            identifier: Saved assay setup identifier.
            payload: Expected revision and optional publication notes.

        Returns:
            Published setup snapshot after its resources are activated atomically.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.publish_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            ),
            lambda actor, sample: self._publish_with_gene_list_access(identifier, payload),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def _publish_with_gene_list_access(
        self, identifier: str, payload: AssaySetupAction
    ) -> dict[str, Any]:
        """Require gene-list edit permission when activation links shared lists.

        Args:
            identifier: Draft or submitted setup identity, checked by the outer operation.
            payload: Expected revision and optional publication notes.

        Returns:
            Published setup after atomic activation.

        Raises:
            AppError: The actor lacks edit permission or publication validation fails.
        """
        service = self._service()
        document = service.get(identifier)
        permissions = (
            ("gene_list.insilico:edit",)
            if document["content"].get("existing_gene_list_ids")
            else None
        )

        def publish(actor: Any, _sample: Any) -> dict[str, Any]:
            """Hold shared gene-list leases while applying their assay associations."""
            with ExitStack() as leases:
                if self._runtime.edit_guard is not None:
                    for gene_list_id in sorted(
                        document["content"].get("existing_gene_list_ids") or []
                    ):
                        release = self._runtime.edit_guard("genelists", gene_list_id, actor, False)
                        if release is not None:
                            leases.callback(release)
                return dict(
                    service.transition(
                        identifier,
                        payload.revision,
                        "publish",
                        actor=actor.username,
                        reason=payload.reason,
                    )
                )

        return self._runtime.execute(
            "assay_setups.activate_associations",
            permissions,
            publish,
        )

    def return_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Return a submitted setup to draft with the caller's explanation.

        Args:
            identifier: Submitted assay setup identifier.
            payload: Expected revision and required explanation for returning to draft.

        Returns:
            Editable draft snapshot at the next revision.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.return_setup",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().transition(
                identifier, payload.revision, "return", actor=actor.username, reason=payload.reason
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )
