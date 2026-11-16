# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized assay groups operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.schemas.assay_groups import (
    AssayGroupCreate,
    AssayGroupStatus,
)

if TYPE_CHECKING:
    from coyote.application.resources.assay_groups import AssayGroupService


class AssayGroups:
    """Authorized assay groups operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], AssayGroupService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def assay_group_impact(self, *, group_id: str) -> dict[str, Any]:
        """Inspect status and affected assays; requires assay.panel:view.

        Args:
            group_id: Registered biological assay-group identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.assay_group_impact",
            ("assay.panel:view",),
            lambda actor, sample: self._service().impact(group_id),
        )

    def change_assay_group_status(
        self, *, group_id: str, payload: AssayGroupStatus
    ) -> dict[str, Any]:
        """Confirm availability with a reason and current revision; requires assay.panel:edit.

        Args:
            group_id: Registered biological assay-group identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.change_assay_group_status",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().change_status(
                group_id, payload, actor=actor.username
            ),
        )

    def list_assay_groups(self) -> dict[str, Any]:
        """List registered system and custom groups; requires assay.panel:view.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.list_assay_groups",
            ("assay.panel:view",),
            lambda actor, sample: self._service().list_payload(),
        )

    def create_assay_group(self, *, payload: AssayGroupCreate) -> dict[str, Any]:
        """Register a custom assay group; requires assay.panel:edit and records an audit event.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.create_assay_group",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().create(payload, actor=actor.username),
        )
