"""Modern shared sections match production while retaining version-four evidence."""

from copy import deepcopy

import pytest
from api_test_support.report_presentation import empty_context, structural_context
from api_test_support.smd_input import document, sections
from coyote.application.reporting.report_renderer import render_report_html
from coyote_api.presentation.reports.branding import render_branded_report_html
from weasyprint import HTML


def test_shared_dna_tables_use_production_columns_and_values():
    """The compact summaries preserve selected findings and their supporting detail cards."""
    inputs = structural_context()
    original = deepcopy(inputs)
    projected = sections(document(inputs))
    assert projected["snvs"]["columns"]["sv"] == [
        "Gen",
        "Mutation",
        "Variantfrekvens",
        "Klassificering",
    ]
    assert projected["snvs"]["rows"] == [
        ["TP53", "p.(K4E)", "40%", "Synthetic clinical significance"]
    ]
    assert projected["cnvs"]["columns"]["sv"] == ["Gen(er)", "Storlek", "Typ", "Kopietal"]
    assert projected["cnvs"]["rows"] == [["MYC", "10000 bp", "DUP", "4"]]
    assert projected["translocations"]["columns"]["sv"] == ["Gener", "HGVS.p"]
    assert projected["snvs"]["cell_options"] == {"0": {"3": {"font_weight": "semibold"}}}
    assert {"snv-0", "cnv-0", "translocation-0"} <= projected.keys()
    assert "50/0" in projected["translocation-0"]["rows"][0]
    assert inputs == original


@pytest.mark.parametrize("size", [-21, -20, 0, 19, 20, 21])
def test_mutation_display_matches_production_indel_boundaries_and_url_decoding(size):
    """Summary and detail boundaries preserve the production 20-base display rules."""
    inputs = structural_context()
    variant = inputs["report_sections_data"]["snvs"][0]
    variant.update(indel_size=size, variant="p.(Ala1%3D)", cdna="c.10A%3EG")
    projected = sections(document(inputs))
    assert projected["snvs"]["rows"][0][1] == ("c.10A%3EG" if size > 20 else "p.(Ala1=)")
    detail = dict(zip(projected["snv-0"]["columns"]["sv"], projected["snv-0"]["rows"][0]))
    assert detail["cDNA-förändring"] == "c.10A>G"
    assert detail["Proteinförändring"] == ("p.(K4E)\np.(Lys4Glu)" if size < 20 else "c.10A%3EG")


@pytest.mark.parametrize(
    "ratio,kind,copy",
    [(0, "DEL", "2"), (0.5, "DUP", "2.82"), (2, "AMP", "8"), (None, "-", "-"), (False, "-", "-")],
)
def test_copy_number_uses_production_rounding_without_replacing_unknown_values(ratio, kind, copy):
    """Display rounding matches production and unavailable ratios never become zero."""
    inputs = structural_context()
    inputs["report_sections_data"]["cnvs"][0]["ratio"] = ratio
    row = sections(document(inputs))["cnvs"]["rows"][0]
    assert row[2:] == [kind, copy]


def test_structural_summary_and_details_use_the_selected_annotation():
    """DNA translocations show one fusion and preserve the picked transcript."""
    inputs = structural_context()
    inputs["report_sections"] = ["TRANSLOCATION"]
    finding = inputs["report_sections_data"]["translocs"][0]
    finding["INFO"]["MANE_ANN"] = {"Gene_Name": "UNSELECTED&GENES", "HGVSp": "wrong"}
    finding["INFO"]["ANN"].append(
        {"Gene_Name": "SYNTHETIC_A&SYNTHETIC_B", "HGVSp": "p.Synthetic", "selected": 1}
    )
    projected = sections(document(inputs))
    assert projected["translocations"]["rows"] == [["SYNTHETIC_A::SYNTHETIC_B", "p.Synthetic"]]
    assert projected["translocation-0"]["record_titles"] == ["SYNTHETIC_A::SYNTHETIC_B"]


def test_dna_document_does_not_render_rna_fusion_data():
    """The RNA namespace cannot enable or populate a DNA translocation section."""
    inputs = structural_context()
    inputs["report_sections"] = ["FUSION"]
    assert "translocations" not in sections(document(inputs))
    inputs["report_sections"] = ["TRANSLOCATION"]
    inputs["report_sections_data"]["fusions"] = inputs["report_sections_data"].pop("translocs")
    projected = sections(document(inputs))
    assert "translocation-0" not in projected


def test_numbered_tables_have_native_matching_captions_and_reference_borders():
    """Applied list order determines the next reference-table number without sorting genes."""
    inputs = empty_context()
    inputs["sample"]["asp_id"] = "synthetic-panel"
    inputs["genes_covered_in_panel"] = {
        "synthetic-panel": {"covered": ["ASSAY_ONLY"]},
        "First": {"covered": ["JAK2", "CALR"]},
        "Second": {"covered": ["MPL"]},
    }
    projected = sections(document(inputs))
    assert (
        projected["gene-list-1"]["caption"] == "Tabell 1: Gener inkluderade i First insilico-panel"
    )
    assert projected["gene-list-1"]["items"] == ["JAK2", "CALR"]
    assert (
        projected["gene-list-2"]["caption"] == "Tabell 2: Gener inkluderade i Second insilico-panel"
    )
    reference = projected["classification"]
    assert reference["caption"] == "Tabell 3: Förklaring av klassificering"
    assert reference["style"] == "reference" and reference["show_header"] is False
    assert reference["column_options"] == {"0": {"width": 12}, "1": {"width": 88}}


def test_governed_question_and_existing_summary_words_survive_compact_presentation():
    """Heading size changes retain the evaluated question, narrative and escaped placeholders."""
    inputs = structural_context()
    inputs["clinical_rule_evaluation"] = {"sections": {"clinical_question": ["<DIAGNOSIS>"]}}
    inputs["latest_sample_comment_text"] = "## Kopietalsprofil:\n\nReviewed narrative."
    html = render_report_html(
        template_name="dna",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    root = HTML(string=html).etree_element
    summary = root.find('.//section[@id="conclusion"]')
    assert summary.find("h2").text == "Slutsats – <DIAGNOSIS>"
    narrative = summary.find("div")
    assert narrative.find(".//h2") is None
    assert narrative.find(".//strong").text == "Kopietalsprofil:"
    assert "Reviewed narrative." in "".join(narrative.itertext())
    assert "&lt;PATIENT_NAME&gt;" in html and "Rapport genererad av" in html


@pytest.mark.parametrize("entity,visible", [("&nbsp;", "\u00a0"), ("&copy;", "©")])
def test_authored_entities_and_markdown_quotes_survive_summary_formatting(entity, visible):
    """Compact headings retain entities and block quotes without reparsing authored HTML."""
    inputs = empty_context()
    inputs["latest_sample_comment_text"] = f"## Heading\n\nText {entity} preserved.\n\n> Quote"
    html = render_report_html(
        template_name="dna",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    summary = HTML(string=html).etree_element.find('.//section[@id="conclusion"]/div')
    assert summary.find(".//strong").text == "Heading"
    assert visible in "".join(summary.itertext())
    assert summary.find(".//blockquote/p").text == "Quote"


def test_header_and_analysis_metadata_use_the_same_configured_laboratory():
    """Center identity is consistent and phone is omitted even when configured."""
    config = {
        "CONTACT": {
            "organization": {
                "name": "Synthetic laboratory",
                "department": "Synthetic department",
                "address": "Synthetic address",
                "phone": "00000000",
            }
        }
    }
    html = render_branded_report_html(
        config=config,
        template_name="dna",
        template_context=empty_context(),
        snapshot_rows=[],
        analyte="dna",
        preview=False,
    )
    assert "Synthetic laboratory och Synthetic department" in html
    assert "Synthetic address" in html
    assert "00000000" not in html


def test_public_gene_references_use_applied_lists_and_version_four_routes():
    """URL text is derived from the configured public base and exact applied list identities."""
    inputs = empty_context()
    inputs["sample"]["asp_id"] = "synthetic-panel"
    inputs["branding"] = {"public_base_url": "https://example.invalid/coyote4"}
    inputs["genes_covered_in_panel"] = {
        "Selected list": {"covered": ["JAK2"]},
        "Temporary": {"covered": ["MPL"], "adhoc": True},
    }
    text = sections(document(inputs))["panel-reference"]["text"]["sv"]
    assert "För analysens genlista, se:" in text
    assert "https://example.invalid/coyote4/public/asp/synthetic-panel/genes" in text
    assert "/public/genelists/Selected%20list/view?assay=synthetic-panel" in text
    assert "Temporary: provspecifik genlista (ingen publik URL)." in text
