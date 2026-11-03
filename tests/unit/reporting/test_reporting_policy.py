"""Report eligibility, scoped annotation selection and governed metadata regressions."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from coyote3.application.common.release_resources import capture_assay_resource
from coyote3.application.reporting.dna_report_payload import filter_variants_for_report
from coyote3.application.reporting.eligibility import reportable_tiers, structural_report_inclusion
from coyote3.application.reporting.report_context import prepare_render_context, report_scope_label
from coyote3.contracts.schemas.assay import ReportableTiersDoc


@pytest.mark.parametrize("value", [[0], [5], [True], [1.5], ["1.0"], None, "1,2"])
def test_tier_policy_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        ReportableTiersDoc(SNV=value)


def test_tier_policy_preserves_empty_and_normalizes_form_selections():
    assert reportable_tiers({}, "SNV") == [1, 2, 3]
    assert reportable_tiers({"reportable_tiers": {"SNV": []}}, "SNV") == []
    assert ReportableTiersDoc(SNV=["3", "1", "3"]).SNV == [1, 3]


def test_report_filter_respects_tiers_genes_and_blacklist():
    variants = [
        {"classification": {"class": tier}, "INFO": {"selected_CSQ": {"SYMBOL": "TP53"}}}
        for tier in [1, 2, 3, 4, 999]
    ]
    variants.append({**deepcopy(variants[0]), "blacklist": True})
    assert [
        v["classification"]["class"] for v in filter_variants_for_report(variants, [], [1, 4])
    ] == [1, 4]
    assert filter_variants_for_report(variants, [], []) == []
    assert filter_variants_for_report(variants, ["BRAF"], [1, 2, 3]) == []
    assert filter_variants_for_report(variants, [], [1, 2, 3], restrict_to_genes=True) == []


def test_renderer_does_not_mutate_aspc_or_duplicate_metadata_in_summary():
    context = {
        "assay_config": {"reporting": {"report_header": "Report"}},
        "report_header": "Report",
        "clinical_rule_evaluation": {
            "sections": {"report_header_suffix": [": paired"], "clinical_question": ["Question"]}
        },
    }
    original = deepcopy(context)
    prepared = prepare_render_context(context, analyte="dna", preview=True)
    assert prepared["assay_config"]["reporting"]["report_header"] == "Report: paired"
    assert prepared["report_header"] == "Report: paired"
    assert context == original


@pytest.mark.parametrize(
    "finding,allowed,expected",
    [
        ({"interesting": True}, [], True),
        ({"classification": {"class": 2}}, [1, 2, 3], True),
        ({"classification": {"class": 4}}, [1, 2, 3], False),
        ({"interesting": True, "classification": {"class": 4}}, [], True),
        ({"fp": True, "interesting": True}, [1, 2, 3], False),
        ({"irrelevant": True, "classification": {"class": 1}}, [1], False),
        ({"classification": {"class": 1, "is_active": False}}, [1], False),
        (
            {"classification": {"class": 1, "is_active": False, "historical_sample_match": True}},
            [1],
            True,
        ),
        ({"blacklist": True, "classification": {"class": 1}}, [1], False),
        ({}, [1, 2, 3], False),
    ],
)
def test_structural_report_selection_preserves_review_exclusions(finding, allowed, expected):
    assert structural_report_inclusion(finding, allowed) is expected


@pytest.mark.parametrize("diagnosis", ["base", "na", "NA"])
@pytest.mark.parametrize("paired", [True, False])
def test_conclusion_scope_uses_captured_panel_for_base_diagnoses(diagnosis, paired):
    panel = {"asp_id": "synthetic", "asp_group": "solid", "display_name": "Synthetic Panel"}
    config = {
        "asp_id": "synthetic",
        "asp_group": "solid",
        "assay_resource_release": capture_assay_resource(panel),
    }
    label = report_scope_label({"diagnosis_id": diagnosis, "paired": paired}, config, None)
    assert label == "Synthetic Panel · " + ("parad analys" if paired else "oparad analys")


def test_conclusion_scope_uses_registered_diagnosis_and_rejects_missing_names():
    sample = {"asp_id": "synthetic", "diagnosis_id": "synthetic-diagnosis", "paired": True}
    repository = SimpleNamespace(
        get_current=lambda assay, diagnosis: {"display_name": "Synthetic Diagnosis"}
    )
    assert report_scope_label(sample, {}, repository) == "Synthetic Diagnosis · parad analys"
    with pytest.raises(ValueError, match="no registered display name"):
        report_scope_label(sample, {}, SimpleNamespace(get_current=lambda *args: None))
