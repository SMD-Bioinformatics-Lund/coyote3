# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized sample administration operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.admin import (
    AdminSampleUpdatePayload,
)
from coyote.domain.identity.assay_access import grants_for

if TYPE_CHECKING:
    from coyote.application.resources.sample import ResourceSampleService


class SampleAdministration:
    """Authorized sample administration operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ResourceSampleService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_admin_samples(
        self,
        *,
        search: str = "",
        asp_group: str = "",
        asp_id: str = "",
        page: int = 1,
        per_page: int = 30,
    ) -> dict[str, Any]:
        """Return the sample list.

        Args:
            search: Free-text search string.
            asp_group: Assay group used to select active, accessible panels; blank text omits the group filter.
            asp_id: Assay-panel identifier used to narrow the active, accessible panels; blank text omits the panel filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:list:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.list_admin_samples",
            ("sample:list:global",),
            lambda actor, sample: self._service().list_payload(
                asp_ids=None if actor.is_superuser else actor.asp_ids,
                assay_access=grants_for(actor),
                search=search,
                asp_group=asp_group,
                asp_id=asp_id,
                page=page,
                per_page=per_page,
            ),
        )

    def admin_sample_context(self, *, sample_id: str) -> dict[str, Any]:
        """Return edit context for an sample.

        Args:
            sample_id: Sample identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (sample:view:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.admin_sample_context",
            ("sample:view:global",),
            lambda actor, sample: self._service().context_payload(sample_id=sample_id),
        )

    def update_sample(self, *, sample_id: str, payload: AdminSampleUpdatePayload) -> dict[str, Any]:
        """Update an sample.

        Args:
            sample_id: Sample identifier to update.
            payload: Submitted sample payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:edit:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.update_sample",
            ("sample:edit:global",),
            lambda actor, sample: self._service().update(
                sample_id=sample_id, payload=payload.model_dump(), actor_username=actor.username
            ),
            edit_resource=("samples", sample_id),
        )

    def delete_sample(self, *, sample_id: str) -> dict[str, Any]:
        """Delete owned sample records and queue generated report files for permanent erasure.

        Args:
            sample_id: Sample identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:delete:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.delete_sample",
            ("sample:delete:global",),
            lambda actor, sample: self._service().delete(sample_id=sample_id),
            edit_resource=("samples", sample_id),
            editing_session_required=False,
        )
