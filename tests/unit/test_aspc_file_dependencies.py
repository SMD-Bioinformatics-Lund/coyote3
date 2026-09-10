"""ASPC capabilities follow the ASP file contract at both UI and save boundaries."""

import pytest

from api.application.resources.aspc import AspcService
from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_form_spec
from api.contracts.schemas.assay import AssaySpecificPanelsDoc
from api.domain.core.exceptions import AppError


def test_saved_empty_file_selection_does_not_reenable_analyses():
    panel = AssaySpecificPanelsDoc.model_validate(
        {
            "asp_id": "synthetic",
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "display_name": "Synthetic",
            "expected_files": [],
            "required_files": [],
        }
    ).model_dump()
    assert panel["expected_files"] == []
    assert AspcService._analysis_types_for_panel(panel, category="dna") == []


@pytest.mark.parametrize(
    "category,family,expected,required,analyses",
    [
        ("dna", "panel-dna", ["vcf_files"], ["cnv"], ["SNV"]),
        (
            "dna",
            "panel-dna",
            ["vcf_files", "transloc"],
            ["vcf_files"],
            ["SNV", "TRANSLOCATION", "FUSION"],
        ),
        ("dna", "panel-dna", [], [], []),
        ("rna", "wts", ["expression_path"], ["fusion_files"], ["EXPRESSION"]),
        ("rna", "panel-rna", ["expression_path"], [], []),
    ],
)
def test_analysis_options_follow_expected_files(category, family, expected, required, analyses):
    panel = {
        "asp_category": category,
        "asp_family": family,
        "expected_files": expected,
        "required_files": required,
    }
    assert AspcService._analysis_types_for_panel(panel, category=category) == analyses


def test_save_rejects_unavailable_analysis_and_disabled_report_section():
    panel = {"asp_category": "dna", "asp_family": "panel-dna", "expected_files": ["vcf_files"]}
    with pytest.raises(AppError, match="input files"):
        AspcService._validate_analysis_types_for_panel({"analysis_types": ["CNV"]}, panel)
    with pytest.raises(AppError, match="Report sections"):
        AspcService._validate_analysis_types_for_panel(
            {"analysis_types": ["SNV"], "reporting": {"report_sections": ["CNV"]}}, panel
        )
    AspcService._validate_analysis_types_for_panel(
        {"analysis_types": ["SNV"], "reporting": {"report_sections": ["SNV"]}}, panel
    )


@pytest.mark.parametrize(
    "resource,identity",
    [
        ("asp", "asp_id"),
        ("aspc_dna", "aspc_id"),
        ("aspc_rna", "aspc_id"),
        ("isgl", "isgl_id"),
        ("role", "name"),
        ("permission", "permission_id"),
    ],
)
def test_identity_is_editable_only_during_creation(resource, identity):
    field = build_form_spec(managed_resource_spec(resource))["fields"][identity]
    assert field["readonly"] is False
    assert field["readonly_mode"] == ["edit"]
    assert "derive_from" not in field
