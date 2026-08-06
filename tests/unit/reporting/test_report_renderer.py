"""Tests for server-side report template rendering."""

from __future__ import annotations

from datetime import date

from api.application.reporting.report_renderer import render_report_html


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


def test_rna_report_renderer_uses_generated_summary_without_reviewed_comment():
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
            "clinical_summary_text": "Inga rapporterbara fusioner påvisades.",
        },
        snapshot_rows=[],
        analyte="rna",
        preview=True,
    )

    assert "Inga rapporterbara fusioner påvisades." in html
    assert "Slutsats saknas!" not in html
    assert "<th>Fusion</th><th>Klassificering</th>" in html
    assert "Detekterade fusioner" in html
