"""Service for sample-scoped biomarker workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.contracts.dna import BiomarkerAssessmentRequest
from coyote3.domain.common.biomarkers import (
    BIOMARKER_ANALYSES,
    BIOMARKER_FIELDS,
    project_biomarkers,
)
from coyote3.domain.common.errors import api_error


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
        payload = self.review_payload(sample=sample)
        analyses = payload["analysis_types"]
        if analysis_type not in BIOMARKER_ANALYSES:
            raise api_error(422, "Unsupported biomarker analysis")
        if analysis_type not in analyses:
            raise api_error(400, "Analysis is not enabled in the sample ASPC")
        analyses = [analysis_type]
        biomarkers = project_biomarkers(payload["biomarkers"], analyses)
        return {
            "sample": sample,
            "meta": {"count": len(biomarkers), "analysis_types": analyses},
            analysis_type.lower(): biomarkers,
        }

    def review_payload(self, *, sample: dict) -> dict:
        """Return only measured biomarker fields enabled in the sample's stored ASPC.

        Args:
            sample: Authorized DNA sample with its immutable configuration selection.

        Returns:
            Enabled analysis names and independently measured biomarker records.

        Raises:
            AppError: The sample is missing, is not DNA, or has invalid configuration.
        """
        if not sample:
            raise api_error(404, "Sample not found")
        if sample.get("asp_category") != "dna":
            raise api_error(400, "Biomarker analyses require a DNA sample")
        config = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )
        analyses = [item for item in config.get("analysis_types", []) if item in BIOMARKER_ANALYSES]
        return {
            "analysis_types": analyses,
            "biomarkers": project_biomarkers(
                self.biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"])),
                analyses,
            ),
        }

    def assign_assessment(
        self,
        *,
        sample: dict,
        record_id: str,
        method: str,
        change: BiomarkerAssessmentRequest,
        actor: str,
    ) -> dict:
        """Save a user assessment without recalculating any measured score.

        Args:
            sample: Authorized DNA sample whose stored ASPC governs enabled measurements.
            record_id: Sample-owned measurement document identifier.
            method: Existing HRD, MSIS, MSIP or TMB measurement to assess independently.
            change: Manual value and last observed assessment revision.
            actor: Trusted current principal's username, never supplied by the client.

        Returns:
            Updated enabled measurements and their current assessments.

        Raises:
            AppError: The measurement is absent/disabled or another editor changed it.
        """
        change = BiomarkerAssessmentRequest.model_validate(change.model_dump())
        payload = self.review_payload(sample=sample)
        fields = {
            field for analysis in payload["analysis_types"] for field in BIOMARKER_FIELDS[analysis]
        }
        record = next(
            (row for row in payload["biomarkers"] if str(row.get("_id")) == record_id), None
        )
        if method not in fields or not record or not isinstance(record.get(method), dict):
            raise api_error(404, "Enabled biomarker measurement not found for this sample")
        assessment = {
            "value": change.value,
            "assessed_by": actor,
            "assessed_at": datetime.now(UTC),
            "revision": change.expected_revision + 1,
        }
        if not self.biomarker_repository.assign_assessment(
            sample_id=str(sample["_id"]),
            record_id=record_id,
            method=method,
            expected_revision=change.expected_revision,
            assessment=assessment,
        ):
            raise api_error(409, "Biomarker assessment changed. Reload before saving again.")
        return self.review_payload(sample=sample)


__all__ = ["BiomarkerService"]
