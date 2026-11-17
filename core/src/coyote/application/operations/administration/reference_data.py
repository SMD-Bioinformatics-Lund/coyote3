# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized field and metadata reads for managed reference resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
)

if TYPE_CHECKING:
    from coyote.application.resources.fields import ResourceFieldService


class ReferenceData:
    """Authorized field and metadata reads for managed reference resources."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ResourceFieldService]
    ) -> None:
        """Bind the current authorization runtime and reference-field implementation."""
        self._runtime, self._service = runtime, service

    def group_metadata(self, group_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            group_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.group_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().group_metadata(group_id),
        )

    def diagnosis_metadata(self, diagnosis_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            diagnosis_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.diagnosis_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().diagnosis_metadata(diagnosis_id),
        )

    def group_field(self, group_id: str, field: GroupField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            group_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.group_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().group_field(group_id, field),
        )

    def diagnosis_field(self, diagnosis_id: str, field: DiagnosisField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            diagnosis_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.diagnosis_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().diagnosis_field(diagnosis_id, field),
        )

    def assay_metadata(self, assay_panel_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            assay_panel_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.assay_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().assay_metadata(assay_panel_id),
        )

    def assay_field(self, assay_panel_id: str, field: AssayField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            assay_panel_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.assay_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().assay_field(assay_panel_id, field),
        )

    def configuration_metadata(self, aspc_id: str) -> Any:
        """Read selected reference data after checking assay.config:view.

        Args:
            aspc_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.configuration_metadata",
            ("assay.config:view",),
            lambda actor, sample: self._service().configuration_metadata(aspc_id),
        )

    def configuration_field(self, aspc_id: str, field: ConfigurationField) -> Any:
        """Read selected reference data after checking assay.config:view.

        Args:
            aspc_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.configuration_field",
            ("assay.config:view",),
            lambda actor, sample: self._service().configuration_field(aspc_id, field),
        )

    def gene_list_metadata(self, genelist_id: str) -> Any:
        """Read selected reference data after checking gene_list.insilico:view.

        Args:
            genelist_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.gene_list_metadata",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().gene_list_metadata(genelist_id),
        )

    def gene_list_field(self, genelist_id: str, field: GeneListField) -> Any:
        """Read selected reference data after checking gene_list.insilico:view.

        Args:
            genelist_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.gene_list_field",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().gene_list_field(genelist_id, field),
        )
