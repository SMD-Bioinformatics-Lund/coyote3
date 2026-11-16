# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized diagnoses operations shared by HTTP and local callers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.schemas.diagnoses import (
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)

if TYPE_CHECKING:
    from coyote.application.resources.diagnoses import DiagnosisService


class Diagnoses:
    """Authorized diagnoses operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], DiagnosisService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_shared_diagnosis(self, *, payload: SharedDiagnosisCreate) -> dict[str, Any]:
        """Create one shared definition and selected assay links; requires assay.panel:edit.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.create_shared_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().create_definition(payload, actor=actor.username),
        )

    def change_diagnosis_association_status(
        self, *, assay_panel_id: str, diagnosis_id: str, payload: DiagnosisAssociationUpdate
    ) -> dict[str, Any]:
        """Enable or disable only this assay link; requires assay.panel:edit.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.change_diagnosis_association_status",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().set_association_status(
                assay_panel_id, diagnosis_id, payload, actor=actor.username
            ),
        )

    def list_shared_diagnoses(self) -> dict[str, Any]:
        """List shared definitions; requires assay.panel:view.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.list_shared_diagnoses",
            ("assay.panel:view",),
            lambda actor, sample: self._service().definitions_payload(),
        )

    def revise_shared_diagnosis(
        self, *, diagnosis_id: str, payload: SharedDiagnosisUpdate
    ) -> dict[str, Any]:
        """Revise shared metadata for all associated assays; requires assay.panel:edit.

        Args:
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.revise_shared_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().revise_definition(
                diagnosis_id, payload, actor=actor.username
            ),
            edit_resource=("diagnoses", diagnosis_id),
        )

    def list_diagnoses(self, *, assay_panel_id: str) -> dict[str, Any]:
        """List current and retired diagnoses; requires assay.panel:view.

        Args:
            assay_panel_id: Registered assay-panel identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.list_diagnoses",
            ("assay.panel:view",),
            lambda actor, sample: self._service().list_payload(assay_panel_id),
        )

    def create_diagnosis(self, *, assay_panel_id: str, payload: DiagnosisCreate) -> dict[str, Any]:
        """Register a diagnosis under an existing assay; requires assay.panel:edit.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.create_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().save(
                assay_panel_id, payload, actor=actor.username
            ),
        )

    def update_diagnosis(
        self, *, assay_panel_id: str, diagnosis_id: str, payload: DiagnosisUpdate
    ) -> dict[str, Any]:
        """Revise or retire a diagnosis; requires assay.panel:edit and its current version.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.update_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().save(
                assay_panel_id, payload, actor=actor.username, diagnosis_id=diagnosis_id
            ),
        )
