"""The import-based report boundary preserves clinical facts and validates resources."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from smd_reports import ReportLoader
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import TextBox

from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_context import prepare_render_context
from coyote3.application.reporting.report_renderer import render_report_html
from coyote3.application.reporting.report_service import template_content_hash
from coyote3.application.reporting.smd_input import build_smd_report_input
from tests.unit.reporting.test_report_presentation import empty_context, structural_context


def document(inputs, analyte="dna", preview=True):
    """Validate the adapter's synthetic input against the installed package contract."""
    prepared = prepare_render_context(inputs, analyte=analyte, preview=preview)
    prepared["report_generated_at"] = datetime(2026, 1, 2, 12, tzinfo=UTC)
    result = build_smd_report_input(
        prepared, analyte=analyte, preview=preview, presentation=ReportPresentation()
    )
    ReportLoader().loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return result


def sections(result):
    """Index projected report sections by their stable clinical role."""
    return {section["key"]: section for section in result["sections"]}


def test_projection_preserves_selected_values_and_does_not_mutate_context():
    inputs = structural_context()
    original = deepcopy(inputs)
    result = document(inputs)
    assert result["preset"] == "coyote3"
    assert "application" not in result
    projected = sections(result)
    assert projected["snvs"]["rows"] == [
        ["TP53", "17", "4/11", "p.(K4E)", "40%", "I", "Synthetic clinical significance"]
    ]
    snv = dict(zip(projected["snv-0"]["columns"]["sv"], projected["snv-0"]["rows"][0]))
    assert snv["Proteinförändring"] == "p.(Lys4Glu)"
    assert snv["Transkript"] == "ENST_SYNTHETIC_001"
    assert snv["cDNA-förändring"] == "c.10A>G"
    assert projected["cnvs"]["rows"][0][2] == "DUP (4.00)"
    assert "50/0" in projected["translocation-0"]["rows"][0]
    assert result["report"]["generated_at"] == "2026-01-02T12:00:00+00:00"
    assert inputs == original


@pytest.mark.parametrize("value,expected", [(None, "-"), ([50, 0], "50/0"), ("50,0", "50,0")])
def test_read_support_preserves_stored_strings_and_zero_counts(value, expected):
    inputs = structural_context()
    inputs["report_sections_data"]["translocs"][0]["GT"][0]["SR"] = value
    detail = sections(document(inputs))["translocation-0"]
    assert dict(zip(detail["columns"]["sv"], detail["rows"][0]))["Split reads (SR)"] == expected


@pytest.mark.parametrize("value", [0, False])
def test_pgx_does_not_replace_zero_or_false_with_another_field(value):
    inputs = empty_context()
    inputs["report_sections_data"]["pgx"] = [
        {"gene": "SYNTHETIC", "result": value, "phenotype": "not the selected result"}
    ]
    projected = sections(document(inputs))
    assert projected["pgx"]["rows"] == [["SYNTHETIC", value]]


def test_disabled_analysis_does_not_leak_supplied_findings():
    inputs = structural_context()
    inputs["report_sections"] = []
    result = document(inputs)
    assert not {"snvs", "snv-0", "cnvs", "cnv-0", "translocations"} & sections(result).keys()
    assert "TP53" not in json.dumps(result)


def test_gene_lists_keep_all_genes_in_order_without_repeating_the_assay_panel():
    inputs = empty_context()
    inputs["sample"]["asp_id"] = "synthetic-panel"
    genes = [f"GENE_{index:03d}" for index in range(31)]
    inputs["genes_covered_in_panel"] = {
        "synthetic-panel": {"covered": ["EXCLUDED_DUPLICATE"]},
        "Synthetic scope": {"covered": genes},
    }
    projected = sections(document(inputs))
    assert "gene-list-0" not in projected
    assert projected["gene-list-1"]["items"] == genes


@pytest.mark.parametrize("count", [0, 31, 503])
def test_compact_gene_table_preserves_every_gene_in_html_and_paginated_pdf(count):
    """Covered genes remain ordered, legible and inside PDF margins as the list grows."""
    inputs = empty_context()
    inputs["report_sections"] = []
    genes = [f"SYNTHETIC_{index:04d}" for index in range(count)]
    inputs["genes_covered_in_panel"] = {"Synthetic scope": {"covered": genes}}
    output = render_report_html(
        template_name="smd/dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    html = HTML(string=output)
    table = html.etree_element.find('.//section[@id="gene-list-0"]/table')
    if count:
        assert table is not None
        assert [cell.text for cell in table.findall(".//td")] == genes
    else:
        assert table is None
        assert html.etree_element.find('.//section[@id="gene-list-0"]/p[@class="empty"]').text
    rendered_genes = []
    for page in html.render().pages:
        bounds = page._page_box
        for box in bounds.descendants():
            if isinstance(box, TextBox) and box.text in genes:
                rendered_genes.append(box.text)
                assert box.position_x >= bounds.content_box_x() - 1
                assert box.position_x + box.width <= bounds.content_box_x() + bounds.width + 1
                assert box.position_y >= bounds.content_box_y() - 1
                assert box.position_y + box.height <= bounds.content_box_y() + bounds.height + 1
    assert rendered_genes == genes


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_narrative_and_legend_are_modality_specific(analyte):
    inputs = empty_context(analyte)
    sentence = "En exakt svensk mening med å, ä och ö."
    inputs["clinical_rule_evaluation"] = {"sections": {"analysis_description": [sentence]}}
    projected = sections(document(inputs, analyte))
    assert projected["description"]["text"] == sentence
    tier_one = projected["classification"]["rows"][0][1]
    assert ("genvarianter som är diagnostiska" in tier_one) is (analyte == "dna")
    assert ("internationella/nationella riktlinjer" in tier_one) is (analyte == "rna")


def test_selected_fusion_call_and_annotation_are_preserved():
    inputs = empty_context("rna")
    inputs["fusions"] = [
        {
            "gene1": "SYNTHETIC_A",
            "gene2": "SYNTHETIC_B",
            "classification": {"class": 3},
            "calls": [
                {"selected": 0, "spanpairs": 999},
                {"selected": 1, "spanpairs": 0, "spanreads": 0},
            ],
            "global_annotations": [
                {"time_created": 1, "text": "Old"},
                {"time_created": 2, "text": "Reviewed annotation"},
            ],
        }
    ]
    detail = sections(document(inputs, "rna"))["fusion-0"]
    values = dict(zip(detail["columns"]["sv"], detail["rows"][0]))
    assert values["Effekt"] == values["Fusionspunkter"] == "NA"
    assert values["Split reads"] == values["Spanning pairs"] == 0
    assert values["Kommentar"] == "Reviewed annotation"
    assert 999 not in detail["rows"][0]


@pytest.mark.parametrize(
    "resource", ["/etc/passwd", "file:///private.svg", "https://example.invalid/logo.png"]
)
def test_adapter_never_passes_paths_or_network_artwork_to_package(resource):
    inputs = empty_context()
    inputs["branding"] = {"center_logo": resource}
    with pytest.raises(ValueError, match="already be embedded"):
        document(inputs)


def test_package_rejects_malformed_embedded_image():
    inputs = empty_context()
    inputs["branding"] = {"center_logo": "data:image/png;base64,bm90IGFuIGltYWdl"}
    with pytest.raises(ValueError):
        document(inputs)


def test_saved_document_omits_preview_and_escapes_untrusted_text():
    inputs = structural_context()
    inputs["report_sections_data"]["snvs"][0]["symbol"] = '<script>alert("unsafe")</script>'
    inputs["latest_sample_comment_text"] = '<img src="https://example.invalid/leak">**Reviewed**'
    output = render_report_html(
        template_name="smd/dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    assert "PREVIEW · UNSAVED REPORT" not in output
    assert "<script>" not in output and '<img src="https:' not in output
    assert "&lt;script&gt;" in output and "<strong>Reviewed</strong>" in output
    assert "Content-Security-Policy" in output
    assert 'name="smd-reports:package_version" content="0.4.0"' in output


def test_smd_identity_is_distinct_from_historical_templates_and_analytes():
    names = [
        "dna_report.html",
        "modern/dna_report.html",
        "smd/dna_report.html",
        "smd/report_fusion.html",
    ]
    hashes = [template_content_hash(name) for name in names]
    assert len(set(hashes)) == len(names)
    assert all(len(digest) == 64 for digest in hashes)
    assert hashes == [template_content_hash(name) for name in names]
