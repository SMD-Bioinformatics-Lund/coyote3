"""Assay declarations constrain configuration capabilities before publication."""

import pytest
from pydantic import ValidationError

from coyote3.application.resources.aspc import AspcService
from coyote3.contracts.schemas.assay import AssaySpecificPanelsDoc
from coyote3.domain.exceptions import AppError


def assay(**changes):
    """Build a synthetic DNA panel with explicitly supported input files."""
    return AssaySpecificPanelsDoc.model_validate(
        {
            "asp_id": "test_panel",
            "asp_group": "solid",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "display_name": "Test panel",
            "expected_files": ["vcf_files", "cnv"],
            **changes,
        }
    )


def test_supported_subset_constrains_configuration():
    panel = assay(supported_analyses=["snv"]).model_dump()
    assert panel["supported_analyses"] == ["SNV"]
    assert AspcService._analysis_types_for_panel(panel, category="dna") == ["SNV"]
    with pytest.raises(AppError, match="Analysis type"):
        AspcService._validate_analysis_types_for_panel({"analysis_types": ["CNV"]}, panel)


def test_empty_subset_is_not_replaced_with_all_capabilities():
    panel = assay(supported_analyses=[]).model_dump()
    assert AspcService._analysis_types_for_panel(panel, category="dna") == []


def test_omitted_subset_resolves_from_registered_inputs():
    assert assay().supported_analyses == ["SNV", "CNV"]


@pytest.mark.parametrize(
    "changes",
    [
        {"asp_family": "panel-rna"},
        {"supported_analyses": ["EXPRESSION"]},
        {"supported_analyses": ["COVERAGE"]},
        {"supported_analyses": ["METHYLATION"]},
        {"expected_files": ["transloc"], "supported_analyses": ["FUSION"]},
    ],
)
def test_invalid_family_or_capability_is_rejected(changes):
    with pytest.raises(ValidationError):
        assay(**changes)


def test_dna_fusion_evidence_uses_translocation_capability():
    """DNA breakend findings have one capability; RNA fusion remains separate."""
    panel = assay(expected_files=["transloc"]).model_dump()
    assert panel["supported_analyses"] == ["TRANSLOCATION"]
    AspcService._validate_analysis_types_for_panel(
        {"analysis_types": ["TRANSLOCATION"], "reporting": {"report_sections": ["TRANSLOCATION"]}},
        panel,
    )
    with pytest.raises(AppError):
        AspcService._validate_analysis_types_for_panel({"analysis_types": ["FUSION"]}, panel)
