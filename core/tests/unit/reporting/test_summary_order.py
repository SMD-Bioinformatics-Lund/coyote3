"""ASPC priorities change presentation independently without changing clinical content."""

from copy import deepcopy

import pytest
from core_test_support.clinical_rules import _context, _document
from core_test_support.report_presentation import empty_context, structural_context
from core_test_support.smd_input import document, sections
from coyote.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote.application.reporting.clinical_rules.service import rendered_summary
from coyote.application.reporting.preview_consistency import preview_fingerprint
from coyote.application.reporting.report_renderer import render_report_html
from coyote.contracts.authoring.forms import build_form_spec
from coyote.contracts.authoring.resources import managed_resource_spec
from coyote.contracts.schemas.assay import AspcReportingDoc
from coyote.contracts.schemas.clinical_rules import ClinicalRuleBlock
from pydantic import ValidationError
from weasyprint import HTML


def reporting(**changes):
    """Supply required reporting fields without an implicit order override."""
    return AspcReportingDoc(
        report_header="Synthetic",
        report_method="Synthetic",
        plots_path="plots",
        report_folder="reports",
        **changes,
    )


@pytest.mark.parametrize("field", ["summary_text_order", "summary_table_order"])
def test_order_defaults_and_canonical_analysis_names(field):
    assert getattr(reporting(), field) == []
    assert getattr(reporting(**{field: [" cnv ", "translocation", "snv"]}), field) == [
        "CNV",
        "TRANSLOCATION",
        "SNV",
    ]


@pytest.mark.parametrize("field", ["summary_text_order", "summary_table_order"])
@pytest.mark.parametrize("value", [None, "CNV,SNV", [""], [True], ["OTHER"], ["snv", "SNV"]])
def test_invalid_or_ambiguous_order_is_rejected(field, value):
    with pytest.raises(ValidationError):
        reporting(**{field: value})


def rules():
    """Publish independent analysis sections between fixed introductory/concluding text."""
    result = _document()
    result.blocks = [
        ClinicalRuleBlock(
            block_id=f"section_{index}",
            name=heading,
            analysis=analysis,
            section=heading,
            section_order=index,
            block_order=1,
            match_strategy="all_matches",
            rules=[
                {
                    "rule_id": f"rule_{index}",
                    "name": heading,
                    "order": 1,
                    "output": [{"type": "text", "value": f"Reviewed {heading}."}],
                }
            ],
        )
        for index, (heading, analysis) in enumerate(
            [
                ("Introduction", None),
                ("SNVs", "SNV"),
                ("CNVs", "CNV"),
                ("Fusions", "TRANSLOCATION"),
                ("Summary", None),
            ]
        )
    ]
    return result


def test_text_order_changes_only_section_presentation_and_retains_fixed_sections():
    context = _context()
    rule_set = rules()
    evaluator = ClinicalRuleEvaluator()
    enabled = {"SNV", "CNV", "TRANSLOCATION"}
    baseline = evaluator.evaluate(context, rule_set, reporting_analyses=enabled)
    context.aspc.reporting.summary_text_order = ["CNV", "TRANSLOCATION", "SNV"]
    ordered = evaluator.evaluate(context, rule_set, reporting_analyses=enabled)
    assert list(baseline.sections) == ["Introduction", "SNVs", "CNVs", "Fusions", "Summary"]
    assert list(ordered.sections) == ["Introduction", "CNVs", "Fusions", "SNVs", "Summary"]
    assert ordered.sections == baseline.sections
    assert ordered.trace == baseline.trace
    assert ordered.source == baseline.source
    text = rendered_summary(ordered)
    assert (
        text.index("Reviewed CNVs.")
        < text.index("Reviewed Fusions.")
        < text.index("Reviewed SNVs.")
    )


def test_partial_text_order_keeps_unlisted_analyses_stable_and_respects_enablement():
    context = _context()
    context.aspc.reporting.summary_text_order = ["TRANSLOCATION", "CNV"]
    result = ClinicalRuleEvaluator().evaluate(context, rules(), reporting_analyses={"SNV", "CNV"})
    assert list(result.sections) == ["Introduction", "CNVs", "SNVs", "Summary"]
    assert "Fusions" not in result.sections


def test_preparation_carries_aspc_text_priority_into_evaluation_facts():
    original = _context()
    aspc = original.aspc.model_dump()
    aspc["reporting"]["summary_text_order"] = ["CNV", "SNV"]
    prepared = prepare_report_context(
        sample=original.sample.model_dump(),
        asp=original.asp.model_dump(),
        aspc=aspc,
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={},
    )
    assert prepared.aspc.reporting.summary_text_order == ["CNV", "SNV"]


def test_shared_sections_keep_their_sentences_and_ignore_disabled_analysis_priorities():
    context = _context()
    context.aspc.reporting.summary_text_order = ["CNV", "TRANSLOCATION", "SNV"]
    rule_set = rules()
    rule_set.blocks[2].section = "SNVs"
    result = ClinicalRuleEvaluator().evaluate(
        context,
        rule_set,
        reporting_analyses={"SNV", "TRANSLOCATION"},
    )
    assert list(result.sections) == ["Introduction", "Fusions", "SNVs", "Summary"]
    assert result.sections["SNVs"] == ["Reviewed SNVs."]
    result = ClinicalRuleEvaluator().evaluate(
        context,
        rule_set,
        reporting_analyses={"SNV", "CNV", "TRANSLOCATION"},
    )
    assert list(result.sections) == ["Introduction", "SNVs", "Fusions", "Summary"]
    assert result.sections["SNVs"] == ["Reviewed SNVs.", "Reviewed CNVs."]


def test_table_order_is_independent_of_text_and_keeps_detail_cards_and_values():
    context = structural_context()
    context["latest_sample_comment_text"] = "Reviewed saved conclusion."
    baseline = document(context)
    context["assay_config"]["reporting"].update(
        summary_text_order=["SNV", "CNV"],
        summary_table_order=["CNV", "TRANSLOCATION", "SNV"],
    )
    original = deepcopy(context)
    ordered = document(context)
    keys = [section["key"] for section in ordered["sections"]]
    assert keys.index("cnvs") < keys.index("translocations") < keys.index("snvs")
    assert sections(ordered) == sections(baseline)
    assert [item["key"] for item in ordered["sections"] if item["kind"] == "details"] == [
        item["key"] for item in baseline["sections"] if item["kind"] == "details"
    ]
    assert context == original
    html = render_report_html(
        template_name="smd/dna_report.html",
        template_context=context,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
    )
    keys = [section.get("id") for section in HTML(string=html).etree_element.findall(".//section")]
    assert keys.index("cnvs") < keys.index("translocations") < keys.index("snvs")


def test_biomarker_rows_follow_table_order_without_reordering_detail_cards():
    context = structural_context()
    context["report_sections"].extend(["HRD", "MSI", "TMB"])
    context["report_sections_data"].update(
        hrd=[{"HRD": {"sum": 3}}],
        msi=[{"MSIP": {"per": 2}}],
        tmb=[{"TMB": {"value": 1}}],
    )
    baseline = document(context)
    context["assay_config"]["reporting"]["summary_table_order"] = ["TMB", "MSI", "HRD", "SNV"]
    ordered = document(context)
    assert [row[0] for row in sections(ordered)["biomarkers"]["rows"]] == ["TMB", "MSIP", "HRD"]
    keys = [section["key"] for section in ordered["sections"]]
    assert keys.index("biomarkers") < keys.index("snvs")
    assert [item for item in ordered["sections"] if item["kind"] == "details"] == [
        item for item in baseline["sections"] if item["kind"] == "details"
    ]


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_unconfigured_order_and_text_only_configuration_keep_table_order(analyte):
    context = empty_context(analyte)
    baseline = document(context, analyte=analyte)
    context["assay_config"]["reporting"]["summary_text_order"] = ["PGX"]
    assert document(context, analyte=analyte) == baseline


def test_rna_table_priority_moves_pgx_without_creating_a_dna_translocation_section():
    context = empty_context("rna")
    context["assay_config"]["reporting"]["summary_table_order"] = ["PGX", "FUSION"]
    keys = [section["key"] for section in document(context, analyte="rna")["sections"]]
    assert keys.index("pgx") < keys.index("fusions")
    assert "translocations" not in keys


@pytest.mark.parametrize("field", ["summary_text_order", "summary_table_order"])
def test_order_change_invalidates_the_reviewed_preview(field):
    context = structural_context()
    original = preview_fingerprint("smd/dna_report.html", context)
    context["assay_config"]["reporting"][field] = ["CNV", "SNV"]
    assert preview_fingerprint("smd/dna_report.html", context) != original


@pytest.mark.parametrize("resource", ["aspc_dna", "aspc_rna"])
def test_both_order_fields_are_available_in_aspc_reporting_forms(resource):
    form = build_form_spec(managed_resource_spec(resource))
    fields = {
        item["key"]: item
        for group in form["fields"]["reporting"]["groups"]
        for item in group["fields"]
    }
    for name in ("summary_text_order", "summary_table_order"):
        assert fields[name]["type"] == "list" and fields[name]["default"] == []
