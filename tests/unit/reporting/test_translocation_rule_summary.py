"""Selected DNA fusion summaries retain source evidence and sentence ordering."""

from copy import deepcopy

import pytest

from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote3.application.reporting.clinical_rules.renderers import render_named
from coyote3.application.reporting.clinical_rules.validation import validate_rule_set
from coyote3.contracts.schemas.clinical_rules import ClinicalAnalysisDeclaration, ClinicalRuleBlock
from tests.unit.reporting.test_clinical_rules import _document

TERMS = {
    "first_prefix": "Vid analysen finner man en genfusion mellan generna ",
    "next_prefix": "Vidare finner man en genfusion mellan generna ",
    "final_prefix": "Slutligen finner man en genfusion mellan generna ",
    "gene_joiner": "och",
    "read_prefix": "i ",
    "paired_read_suffix": "% av överspännande läsningar",
    "split_read_suffix": "% av splittade läsningar",
    "support_joiner": " och ",
    "unique_with_support": " samt uppskattas det finnas ",
    "unique_without_support": " i vilken det uppskattas finnas ",
    "unique_suffix": " unika läsningar",
    "evidence_open": " (",
    "evidence_close": ")",
    "sentence_joiner": "\n",
}


def _context(rows):
    """Prepare synthetic structural calls through the production report boundary."""
    return prepare_report_context(
        sample={"name": "SYNTHETIC_FUSION", "asp_id": "assay_1"},
        asp={},
        aspc={"reporting": {"report_sections": ["TRANSLOCATION"]}},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={"translocs": rows},
    )


def _call(genes="BCR&ABL1", **kwargs):
    """Build an explicitly selected call with legacy annotation and evidence fields."""
    return {"interesting": True, "INFO": {"ANN": [{"Gene_Name": genes}]}, **kwargs}


def _render(context):
    """Render the projected groups using the source Swedish fragments."""
    return render_named(
        "translocation_summary",
        source=[group.model_dump() for group in context.aggregates.translocation_summaries],
        scope={},
        terminology={"translocation_summary": TERMS},
    )


def test_selected_gene_pairs_merge_maximum_support_without_modifying_findings():
    """Duplicate calls combine evidence; unselected and incomplete pairs do not narrate."""
    rows = [
        _call(GT=[{"PR": "8,2", "SR": "9,1"}]),
        _call(
            GT=[{"PR": "9,1", "SR": "7,3"}], INFO={"MANE_ANN": {"Gene_Name": "BCR&ABL1"}, "UR": 12}
        ),
        _call("ETV6&NTRK3", interesting=False),
        _call("BCR"),
    ]
    original = deepcopy(rows)
    context = _context(rows)
    assert rows == original
    assert context.aggregates.translocation_summary_count == 1
    assert _render(context) == (
        "Vid analysen finner man en genfusion mellan generna BCR och ABL1 "
        "(i 20.0% av överspännande läsningar och 30.0% av splittade läsningar"
        " samt uppskattas det finnas 12 unika läsningar)"
    )


@pytest.mark.parametrize("raw", [None, "", "bad", "0,0", "-1,2", "nan,2", "inf,2", "1.5,2"])
def test_invalid_support_never_creates_evidence(raw):
    """Invalid and missing read counts do not fabricate percentages."""
    context = _context([_call(GT=[{"PR": raw, "SR": raw}])])
    group = context.aggregates.translocation_summaries[0]
    assert group.paired_read_percent is None
    assert group.split_read_percent is None
    assert _render(context) == "Vid analysen finner man en genfusion mellan generna BCR och ABL1"


@pytest.mark.parametrize("unique", [-1, float("nan"), float("inf")])
def test_invalid_unique_read_counts_are_not_reported(unique):
    """Negative and nonfinite unique counts cannot become clinical read evidence."""
    row = _call()
    row["INFO"]["UR"] = unique
    group = _context([row]).aggregates.translocation_summaries[0]
    assert group.unique_reads is None


@pytest.mark.parametrize(
    "gt,ur,expected",
    [
        ({"PR": "8,2"}, None, "i 20.0% av överspännande läsningar"),
        ({"SR": "8,2"}, None, "i 20.0% av splittade läsningar"),
        ({}, 7, " i vilken det uppskattas finnas 7 unika läsningar"),
    ],
)
def test_independent_evidence_branches(gt, ur, expected):
    """PR, SR and UR-only sentences use the existing source formations."""
    row = _call(GT=[gt])
    row["INFO"]["UR"] = ur
    assert _render(_context([row])).endswith("(" + expected + ")")


@pytest.mark.parametrize("count", [2, 3])
def test_each_group_has_a_complete_first_next_or_final_sentence(count):
    """Correct the old missing continuation lead for multiple DNA fusions."""
    context = _context([_call(f"GENE{i}&PARTNER{i}") for i in range(count)])
    lines = _render(context).splitlines()
    assert lines[0].startswith("Vid analysen finner man")
    assert lines[1].startswith("Vidare finner man")
    if count == 3:
        assert lines[2].startswith("Slutligen finner man")


def test_registered_renderer_validates_and_evaluates_only_enabled_analysis():
    """The imported rule dispatches typed groups and respects report-section selection."""
    document = _document()
    document.analysis_declarations = {
        "TRANSLOCATION": ClinicalAnalysisDeclaration(narrative="enabled")
    }
    document.terminology = {"translocation_summary": TERMS}
    document.blocks = [
        ClinicalRuleBlock.model_validate(
            {
                "block_id": "dna_fusions",
                "name": "DNA fusion summary",
                "analysis": "TRANSLOCATION",
                "section": "summary",
                "section_order": 10,
                "block_order": 10,
                "match_strategy": "all_matches",
                "rules": [
                    {
                        "rule_id": "selected_pairs",
                        "name": "Selected gene pairs",
                        "order": 1,
                        "condition": {
                            "type": "predicate",
                            "fact": "aggregates.translocation_summary_count",
                            "operator": "gt",
                            "value": 0,
                        },
                        "output": [{"type": "renderer", "name": "translocation_summary"}],
                    }
                ],
            }
        )
    ]
    assert validate_rule_set(document).valid
    context = _context([_call()])
    result = ClinicalRuleEvaluator().evaluate(
        context, document, reporting_analyses={"TRANSLOCATION"}
    )
    assert result.sections["summary"] == [_render(context)]
    disabled = ClinicalRuleEvaluator().evaluate(context, document, reporting_analyses=set())
    assert disabled.sections == {}
