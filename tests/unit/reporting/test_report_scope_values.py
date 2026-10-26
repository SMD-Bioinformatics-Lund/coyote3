"""Dynamic report wording must reflect selected resources rather than finding counts."""

import pytest

from coyote3.application.reporting.clinical_rules.evaluator import render_rule
from coyote3.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote3.application.reporting.clinical_rules.registry import validate_fact_path
from coyote3.contracts.schemas.clinical_rules import ClinicalRule


def context():
    """Prepare overlapping SNV lists and an independent CNV selection."""
    return prepare_report_context(
        sample={"asp_id": "synthetic", "paired": True},
        asp={
            "display_name": "Synthetic full panel",
            "name": "SYN",
            "covered_genes": ["A", "B", "C", "C"],
            "germline_genes": ["B"],
        },
        aspc={},
        analyte="dna",
        report_sections_data={},
        applied_gene_lists=[
            {
                "isgl_id": "one",
                "name": "ONE",
                "displayname": "First list",
                "genes": ["A", "B"],
                "selected_for": ["snv"],
            },
            {
                "isgl_id": "two",
                "name": "TWO",
                "displayname": "Second list",
                "genes": ["B", "C"],
                "selected_for": ["snv"],
            },
            {
                "isgl_id": "cnv",
                "name": "CN",
                "displayname": "CNV list",
                "genes": ["D"],
                "selected_for": ["cnv"],
            },
        ],
    )


def test_report_scope_counts_unique_genes_by_selected_analysis():
    prepared = context()
    assert prepared.asp.covered_genes_count == 3
    assert prepared.gene_lists["snv"].gene_count == 3
    assert prepared.gene_lists["cnv"].gene_count == 1
    assert prepared.gene_lists["snv"].germline_genes == ["B"]
    assert prepared.aggregates.finding_count == 0
    assert prepared.applied_gene_lists[0].name == "ONE"
    assert prepared.applied_gene_lists[0].gene_count == 2


def test_dynamic_text_uses_full_name_short_names_and_unique_count():
    nodes = [
        {"type": "fact", "path": "asp.display_name"},
        {"type": "text", "value": ": "},
        {"type": "list", "path": "gene_lists.snv.names", "conjunction": "and"},
        {"type": "text", "value": " ("},
        {"type": "number", "path": "gene_lists.snv.gene_count", "precision": 0},
        {"type": "text", "value": " genes)"},
    ]
    rule = ClinicalRule(rule_id="scope", name="Scope", order=1, output=nodes)
    assert (
        render_rule(rule, scope=context().evaluation_scope(), terminology={})
        == "Synthetic full panel: ONE and TWO (3 genes)"
    )
    for node in nodes:
        if "path" in node:
            validate_fact_path(node["path"], scope="once")


def test_missing_assay_short_name_is_not_replaced_with_an_identifier():
    prepared = prepare_report_context(
        sample={}, asp={}, aspc={}, analyte="dna", applied_gene_lists=[], report_sections_data={}
    )
    assert prepared.asp.name is None
    assert prepared.asp.covered_genes_count is None
    rule = ClinicalRule(
        rule_id="short",
        name="Short",
        order=1,
        output=[{"type": "fact", "path": "asp.name", "missing": "error"}],
    )
    with pytest.raises(ValueError, match="missing"):
        render_rule(rule, scope=prepared.evaluation_scope(), terminology={})


def test_missing_selected_list_name_cannot_silently_drop_a_list_from_report_wording():
    prepared = prepare_report_context(
        sample={},
        asp={},
        aspc={},
        analyte="dna",
        report_sections_data={},
        applied_gene_lists=[
            {"isgl_id": "named", "name": "Named", "genes": ["A"], "selected_for": ["snv"]},
            {"isgl_id": "unnamed", "genes": ["B"], "selected_for": ["snv"]},
        ],
    )
    assert prepared.gene_lists["snv"].names is None
    assert prepared.gene_lists["snv"].ids == ["named", "unnamed"]
    rule = ClinicalRule(
        rule_id="names",
        name="Names",
        order=1,
        output=[{"type": "list", "path": "gene_lists.snv.names", "missing": "error"}],
    )
    with pytest.raises(ValueError, match="missing"):
        render_rule(rule, scope=prepared.evaluation_scope(), terminology={})
