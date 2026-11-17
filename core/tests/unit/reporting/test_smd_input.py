"""The import-based report boundary preserves clinical facts and validates resources."""

import json
from copy import deepcopy

import pytest
from core_test_support.report_presentation import empty_context, structural_context
from core_test_support.smd_input import document, sections
from coyote.application.reporting.report_renderer import render_report_html
from coyote.application.reporting.report_service import template_content_hash
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import TextBox


def test_projection_preserves_selected_values_and_does_not_mutate_context():
    inputs = structural_context()
    original = deepcopy(inputs)
    result = document(inputs)
    assert result["preset"] == "coyote3"
    assert result["branding"]["application_name"] == "Coyote"
    assert result["branding"]["application_suffix"] == "4"
    assert "application" not in result
    projected = sections(result)
    assert projected["snvs"]["rows"] == [
        ["TP53", "p.(K4E)", "40%", "Synthetic clinical significance"]
    ]
    snv = dict(zip(projected["snv-0"]["columns"]["sv"], projected["snv-0"]["rows"][0]))
    assert snv["Proteinförändring"] == "p.(K4E)\np.(Lys4Glu)"
    assert snv["Transkript"] == "ENST_SYNTHETIC_001, exon 4/11"
    assert snv["cDNA-förändring"] == "c.10A>G"
    assert projected["cnvs"]["rows"][0] == ["MYC", "10000 bp", "DUP", "4"]
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
        template_name="dna",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    html = HTML(string=output)
    table = html.etree_element.find('.//section[@id="gene-list-0"]//table')
    if count:
        assert table is not None
        assert [
            cell.find("span").text
            for cell in table.findall(".//td")
            if cell.find("span") is not None
        ] == genes
    else:
        assert table is None
        assert html.etree_element.find('.//section[@id="gene-list-0"]//p[@class="empty"]').text
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
    assert projected["description"]["text"] == {"sv": sentence}
    tier_one = projected["classification"]["rows"][0][1]
    assert ("genmutationer som är diagnostiska" in tier_one) is (analyte == "dna")
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
    assert values["Antal läsningar"] == values["Antal läs-par"] == 0
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
        template_name="dna",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    assert "PREVIEW · UNSAVED REPORT" not in output
    assert "<script>" not in output and '<img src="https:' not in output
    assert "&lt;script&gt;" in output and "<strong>Reviewed</strong>" in output
    assert "Content-Security-Policy" in output
    assert 'name="smd-reports:package_version" content="0.5.3"' in output


def test_new_profile_suggestions_do_not_replace_the_reviewed_conclusion():
    inputs = structural_context()
    inputs["latest_sample_comment_text"] = "Reviewed synthetic conclusion"
    inputs["clinical_rule_evaluation"] = {
        "sections": {"germline_results": ["New synthetic profile suggestion"]}
    }
    conclusion = sections(document(inputs))["conclusion"]["text"]
    assert "Reviewed synthetic conclusion" in conclusion
    assert "New synthetic profile suggestion" not in conclusion


def test_smd_identity_is_stable_and_distinct_between_analytes():
    names = [
        "dna",
        "rna",
    ]
    hashes = [template_content_hash(name) for name in names]
    assert hashes[0] != hashes[1]
    assert all(len(digest) == 64 for digest in hashes)
    assert hashes == [template_content_hash(name) for name in names]
