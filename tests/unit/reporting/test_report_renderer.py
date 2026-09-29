"""Tests for server-side report template rendering."""

from __future__ import annotations

from datetime import date

import pytest

from api.application.reporting.report_renderer import render_report_html


@pytest.mark.parametrize(
    "analyte,template", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_report_metadata_is_escaped_and_absent_destinations_are_omitted(analyte, template):
    context = {
        "sample": {"name": "synthetic", "case": {}, "control": {}},
        "assay_config": {"reporting": {"report_header": "Report"}},
        "report_header": "Report",
        "report_sections": [],
        "report_sections_data": {},
        "fusions": [],
        "genes_covered_in_panel": {},
    }

    def render():
        return render_report_html(
            template_name=template,
            template_context=context,
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
        )

    assert "Frågeställning" not in render()
    context["clinical_rule_evaluation"] = {
        "sections": {"clinical_question": ["<Question>"], "report_header_suffix": [": <paired>"]}
    }
    html = render()
    assert "&lt;Question&gt;" in html
    assert "Report: &lt;paired&gt;" in html
    assert "<Question>" not in html


@pytest.mark.parametrize(
    "analyte,template", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_report_identity_comes_from_explicit_runtime_values(analyte, template):
    """Both report formats escape runtime identities instead of assuming a center or user."""
    html = render_report_html(
        template_name=template,
        template_context={
            "sample": {"name": "synthetic", "case": {}, "control": {}},
            "assay_config": {"reporting": {}},
            "report_sections": [],
            "report_sections_data": {},
            "fusions": [],
            "genes_covered_in_panel": {},
        },
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        organization_name="Example Lab <research>",
        generated_by="Reviewer <one>",
    )
    assert "Example Lab &lt;research&gt;" in html
    assert "Reviewer &lt;one&gt;" in html
    assert "Centrum för molekylär diagnostik" not in html
    assert "$SCRIPT_ROOT" not in html


def test_dna_report_renderer_uses_master_style_template():
    """Render DNA reports with the master report layout and clinical section labels."""
    html = render_report_html(
        template_name="dna_report.html",
        template_context={
            "assay_config": {
                "reporting": {
                    "report_header": "DNA report",
                    "report_method": "Panel sequencing",
                    "report_description": "Analysis description",
                }
            },
            "report_sections": ["SNV"],
            "report_sections_data": {
                "snvs": [
                    {
                        "symbol": "FLT3",
                        "indel_size": 0,
                        "variant": "p.Asp835Tyr",
                        "cdna": "c.2503G>T",
                        "af": 0.42,
                        "class_short_desc": "Stark klinisk signifikans",
                        "class_long_desc": "Variant av stark klinisk signifikans",
                        "class": 1,
                        "class_type": "Somatisk",
                        "variant_class": "SNV",
                        "feature": "NM_004119",
                        "consequence": "missense",
                        "exon": ["20"],
                        "intron": [],
                        "chr": "13",
                        "pos": 28608258,
                        "var_type": "snv",
                        "protein_changes": ["p.Asp835Tyr"],
                        "global_annotations": [],
                        "annotations_interesting": {},
                    }
                ]
            },
            "sample": {
                "name": "seed_case",
                "case_id": "seed_case",
                "control_id": "seed_control",
                "sample_no": 2,
                "case": {"clarity_id": "GEN_CASE"},
                "control": {"clarity_id": "GEN_CTRL"},
                "assay": "hema_gmsv1",
                "comments": [{"text": "Clinical conclusion", "hidden": 0}],
            },
            "report_date": date(2026, 7, 15),
            "report_timestamp": "260715120000",
            "sample_assay": "hema_gmsv1",
            "assay_group": "hematology",
            "genes_covered_in_panel": {},
            "latest_sample_comment_text": "Latest sample conclusion",
        },
        snapshot_rows=[],
        analyte="dna",
        preview=True,
    )

    assert "*** PREVIEW OF REPORT ***" in html
    assert "Analysresultat" in html
    assert "Kliniskt relevanta SNVs och små INDELs" in html
    assert "Slutsats" in html
    assert "Detekterade mutationer" in html
    assert "Analysbeskrivning" in html
    assert "table.report_general" in html
    assert "Latest sample conclusion" in html
    assert "Clinical conclusion" not in html


def test_rna_report_renderer_leaves_conclusion_empty_without_sample_comment():
    html = render_report_html(
        template_name="report_fusion.html",
        template_context={
            "assay_config": {
                "reporting": {
                    "report_method": "RNA fusion analysis",
                    "report_description": "Fusion analysis",
                }
            },
            "fusions": [],
            "report_header": "RNA report",
            "sample": {
                "name": "seed_rna_case",
                "comments": [],
            },
            "class_desc": {},
            "class_desc_short": {},
            "report_date": date(2026, 7, 15),
            "latest_sample_comment_text": "",
        },
        snapshot_rows=[],
        analyte="rna",
        preview=True,
    )

    assert "Inga rapporterbara fusioner påvisades." not in html
    assert "Slutsats saknas!" not in html
    assert "<th>Fusion</th><th>Klassificering</th>" in html
    assert "Detekterade fusioner" in html


def test_rna_report_renderer_uses_only_latest_sample_comment_for_conclusion():
    html = render_report_html(
        template_name="report_fusion.html",
        template_context={
            "assay_config": {"reporting": {}},
            "fusions": [],
            "report_header": "RNA report",
            "sample": {"name": "seed_rna_case", "comments": [{"text": "Older comment"}]},
            "class_desc": {},
            "class_desc_short": {},
            "report_date": date(2026, 7, 15),
            "latest_sample_comment_text": "Latest reviewer conclusion",
        },
        snapshot_rows=[],
        analyte="rna",
        preview=True,
    )

    assert "Latest reviewer conclusion" in html
    assert "Older comment" not in html
