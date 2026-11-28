# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authoring scope options and registration checks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from coyote.application.classification.bulk_annotation_rules import (
    bulk_annotation_group_options,
)
from coyote.application.reporting.clinical_rules.registry import BULK_ANNOTATION_FACT_PATHS
from coyote.config.constants import DIAGNOSIS_BASE_ID, ENVIRONMENT_OPTIONS
from coyote.contracts.schemas.clinical_rules import (
    BulkAnnotationGroupOption,
    ClinicalRuleDraftCreate,
)
from coyote.domain.common.errors import api_error
from coyote.domain.common.reporting import (
    STANDARD_CNV_SUMMARY_PHRASES,
    STANDARD_TIER_SUMMARY_PHRASES,
)
from coyote.domain.common.resource_names import short_resource_name

from .assignments import ReviewAssignments


class RuleScopeCatalog:
    """Supply assay, diagnosis and group choices for reporting-rule authors."""

    def __init__(
        self,
        *,
        assay_panel_repository: Any = None,
        assay_diagnosis_repository: Any = None,
        assay_group_repository: Any = None,
        assignments: ReviewAssignments,
    ) -> None:
        """Bind the authoritative scope registries and reviewer option provider."""
        self.assay_panel_repository = assay_panel_repository
        self.assay_diagnosis_repository = assay_diagnosis_repository
        self.assay_group_repository = assay_group_repository
        self.assignments = assignments

    def options(self) -> dict[str, Any]:
        """Return authoring scopes and optional sentence wording for explicit draft insertion."""
        group_options = self.annotation_groups()
        group_ids = [group.group_id for group in group_options]
        group_values = (
            {
                path: group_ids
                for path in (
                    "asp.asp_group",
                    "asp.parent_group_id",
                    "asp.ancestor_group_ids",
                    "asp.group_path_ids",
                    "asp.root_group_id",
                )
            }
            if group_ids
            else {}
        )
        sentence_terminology = {
            "sv": {
                "tier_summary": {
                    **deepcopy(STANDARD_TIER_SUMMARY_PHRASES),
                    "single_gene_always_read_context": True,
                },
                "cnv_summary": deepcopy(STANDARD_CNV_SUMMARY_PHRASES),
            }
        }
        if self.assay_panel_repository is None:
            return {
                "assays": [],
                "condition_values": group_values,
                "sentence_terminology": sentence_terminology,
                "bulk_annotation_fact_paths": sorted(BULK_ANNOTATION_FACT_PATHS),
                "bulk_annotation_groups": [
                    group.model_dump(mode="python") for group in group_options
                ],
                **self.assignments.options(),
            }
        assays = []
        for panel in self.panels():
            analyte = str(panel.get("asp_category") or "").lower()
            if analyte not in {"dna", "rna"}:
                continue
            asp_id = str(panel.get("asp_id") or "").strip()
            if not asp_id:
                continue
            assays.append(
                {
                    "asp_id": asp_id,
                    "display_name": str(panel.get("display_name") or asp_id),
                    "name": short_resource_name(panel, asp_id),
                    "analyte": analyte,
                    "diagnoses": [
                        {
                            "diagnosis_id": scope["diagnosis_id"],
                            "display_name": scope["display_name"],
                        }
                        for scope in self.diagnoses(asp_id)
                    ],
                }
            )
        diagnoses = sorted(
            {scope["diagnosis_id"] for assay in assays for scope in assay["diagnoses"]}
        )
        groups = sorted(
            {str(panel.get("asp_group") or "").strip() for panel in self.panels()} - {""}
        )
        return {
            "sentence_terminology": sentence_terminology,
            "bulk_annotation_fact_paths": sorted(BULK_ANNOTATION_FACT_PATHS),
            "bulk_annotation_groups": [group.model_dump(mode="python") for group in group_options],
            "assays": sorted(assays, key=lambda item: (item["display_name"], item["asp_id"])),
            "condition_values": {
                "sample.asp_id": [item["asp_id"] for item in assays],
                "sample.diagnosis_id": diagnoses,
                "sample.environment": list(ENVIRONMENT_OPTIONS),
                "asp.asp_group": groups,
                **group_values,
            },
            **self.assignments.options(),
        }

    def annotation_groups(self) -> list[BulkAnnotationGroupOption]:
        """Read the full registered biological tree without exposing private audit fields.

        Returns:
            Complete group paths, or an empty list without a group repository.

        Raises:
            AppError: A registry hierarchy is incomplete or cyclic.
        """
        try:
            return (
                bulk_annotation_group_options(self.assay_group_repository.list())
                if self.assay_group_repository is not None
                else []
            )
        except ValueError as exc:
            raise api_error(422, "Biological group hierarchy is invalid", str(exc)) from exc

    def panels(self) -> list[dict[str, Any]]:
        """Return installed active assays for rule authoring."""
        return list(self.assay_panel_repository.get_all_asps(is_active=True))

    def diagnoses(self, asp_id: str) -> list[dict[str, Any]]:
        """Return active registered scopes; fail closed when the repository is not configured."""
        if self.assay_diagnosis_repository is None:
            raise RuntimeError("Assay diagnosis repository is required for rule authoring")
        return [{"diagnosis_id": DIAGNOSIS_BASE_ID, "display_name": "Base"}] + [
            row
            for row in self.assay_diagnosis_repository.list_for_assay(asp_id, active_only=True)
            if row["diagnosis_id"] != DIAGNOSIS_BASE_ID
        ]

    def validate(
        self, payload: ClinicalRuleDraftCreate, *, allow_unregistered: bool = False
    ) -> None:
        """Check assay compatibility, optionally accepting a planned assay for authoring.

        Args:
            payload: Draft request; an absent scope skips validation here.
            allow_unregistered: Permit a missing assay while authoring a draft;
                existing inactive or incompatible assays are still rejected.

        Raises:
            AppError: With status 409 for an unavailable assay or analyte mismatch.
        """
        if self.assay_panel_repository is None or payload.scope is None:
            return
        panel = self.assay_panel_repository.get_asp(payload.scope.asp_id)
        if panel is None and allow_unregistered:
            return
        if not panel or panel.get("is_active") is False:
            raise api_error(409, "Clinical rule sets require an active assay panel")
        analyte = str(panel.get("asp_category") or "").lower()
        if analyte != payload.scope.analyte:
            raise api_error(409, "Clinical rule-set analyte does not match the assay panel")
        if payload.scope.diagnosis_id not in {
            scope["diagnosis_id"] for scope in self.diagnoses(payload.scope.asp_id)
        }:
            raise api_error(409, "Select an active registered diagnosis for this assay")
