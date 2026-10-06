"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.domain.common.biomarkers import BIOMARKER_ANALYSES, project_biomarkers
from api.domain.common.errors import api_error


class BiomarkerService:
    """Provide biomarker workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "BiomarkerService":
        """Build the service from the runtime store."""
        return cls(
            biomarker_repository=store.biomarker_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
        )

    def __init__(
        self,
        *,
        biomarker_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: Any,
    ) -> None:
        """Bind measurement reads and revision-aware assay configuration lookup.

        Args:
            biomarker_repository: Reads sample-scoped measurements.
            assay_panel_repository: Resolves the sample's physical assay.
            assay_configuration_repository: Resolves the stored ASPC revision.
        """
        self.biomarker_repository = biomarker_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository

    def list_payload(self, *, sample: dict, analysis_type: str) -> dict:
        """Return biomarker data for a sample.

        Args:
            sample: Sample payload used for biomarker lookup.
            analysis_type: HRD, MSI, or TMB; must be enabled in the stored ASPC.

        Returns:
            dict: Biomarker payload with sample metadata.

        Raises:
            AppError: The sample is absent, is not DNA, or the requested analysis
                is unsupported or disabled in its configuration.
        """
        if not sample:
            raise api_error(404, "Sample not found")
        if sample.get("omics_layer") != "dna":
            raise api_error(400, "Biomarker analyses require a DNA sample")
        config = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )
        analyses = [item for item in config.get("analysis_types", []) if item in BIOMARKER_ANALYSES]
        if analysis_type not in BIOMARKER_ANALYSES:
            raise api_error(422, "Unsupported biomarker analysis")
        if analysis_type not in analyses:
            raise api_error(400, "Analysis is not enabled in the sample ASPC")
        analyses = [analysis_type]
        biomarkers = project_biomarkers(
            self.biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"])), analyses
        )
        return {
            "sample": sample,
            "meta": {"count": len(biomarkers), "analysis_types": analyses},
            analysis_type.lower(): biomarkers,
        }


__all__ = ["BiomarkerService"]
