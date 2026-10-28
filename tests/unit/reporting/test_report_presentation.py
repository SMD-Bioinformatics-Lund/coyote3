"""Modern empty-result wording and compact metadata preserve clinical content."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import TableCellBox, TableRowBox, TextBox

from api.config import report_presentation
from api.presentation.reports.branding import render_branded_report_html
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_renderer import render_report_html
from tests.unit.reporting.test_external_report_templates import context


def empty_context(analyte="dna"):
    """Prepare enabled sections with no reportable findings and complete metadata."""
    inputs = context()
    inputs["sample"].update(
        case_id="SYNTHETIC_CASE",
        control_id="SYNTHETIC_CONTROL",
        sample_no=2,
    )
    inputs["assay_config"]["reporting"]["report_method"] = "Synthetic method"
    inputs["report_date"] = "2026-10-25"
    inputs["report_timestamp"] = "SYNTHETIC_REPORT_ID"
    inputs["report_sections"] = [
        "SNV",
        "CNV",
        "TRANSLOCATION",
        "HRD",
        "MSI",
        "TMB",
        "BIOMARKER",
        "PGX",
    ]
    inputs["report_sections_data"] = {
        "snvs": [],
        "germline_snvs": [],
        "cnvs": [],
        "translocs": [],
        "hrd": [],
        "msi": [],
        "tmb": [],
        "biomarkers": [],
        "pgx": [],
    }
    if analyte == "rna":
        inputs["report_sections"] = ["FUSION", "PGX"]
        inputs["pgx"] = []
    return inputs


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_markdown_conclusion_preserves_formatting_and_renders_bordered_table(analyte):
    """Authored Markdown keeps its structure and prints a legible table in the conclusion."""
    inputs = empty_context(analyte)
    inputs["latest_sample_comment_text"] = (
        "## Synthetic conclusion\n\n**Reviewed** with *context*.\n\n"
        "- First item\n- Second item\n\n"
        "> Synthetic quotation\n\n"
        "| Column | Value |\n| --- | --- |\n| item | result |\n"
    )
    html = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
    )
    for fragment in (
        "<h2>Synthetic conclusion</h2>",
        "<strong>Reviewed</strong>",
        "<em>context</em>",
        "<ul>",
        "<li>First item</li>",
        "<blockquote>",
        "<th>Column</th>",
        "<td>result</td>",
    ):
        assert fragment in html
    document = HTML(string=html).render()
    cells = []
    for page in document.pages:
        for box in page._page_box.descendants():
            if not isinstance(box, TableCellBox):
                continue
            text = "".join(child.text for child in box.descendants() if isinstance(child, TextBox))
            if text in {"Column", "Value", "item", "result"}:
                cells.append(box)
                assert box.border_top_width > 0
                assert box.border_right_width > 0
                assert box.border_bottom_width > 0
                assert box.border_left_width > 0
    assert len(cells) == 4


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_empty_enabled_sections_show_configured_text_without_tables(analyte):
    inputs = empty_context(analyte)
    original = deepcopy(inputs)
    defaults = ReportPresentation().empty_results.model_dump()
    messages = {key: f"Synthetic {key} <empty> & result" for key in defaults}
    output = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
        presentation=ReportPresentation(empty_results=messages),
    )
    document = HTML(string=output).etree_element
    assert not document.findall('.//table[@class="variant_table"]')
    paragraphs = [
        "".join(node.itertext()) for node in document.findall('.//p[@class="report-empty-result"]')
    ]
    expected_keys = defaults.keys() - {"FUSION"} if analyte == "dna" else {"FUSION", "PGX"}
    assert set(paragraphs) == {messages[key] for key in expected_keys}
    assert len(paragraphs) == len(expected_keys)
    assert "<empty>" not in output
    assert "Detekterade fusioner" not in "".join(document.itertext())
    assert inputs == original


def test_disabled_sections_do_not_emit_empty_messages():
    inputs = empty_context()
    inputs["report_sections"] = []
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    assert not HTML(string=output).etree_element.findall('.//p[@class="report-empty-result"]')


def test_populated_dna_sections_retain_every_finding_table():
    inputs = empty_context()
    variant = {
        "symbol": "SYNTHETIC_GENE",
        "variant": "p.Synthetic",
        "cdna": "c.Synthetic",
        "af": 0.5,
        "indel_size": 0,
        "class_short_desc": "Synthetic class",
        "class": 999,
        "global_annotations": [],
        "protein_changes": [],
    }
    inputs["report_sections_data"].update(
        snvs=[variant],
        germline_snvs=[variant],
        cnvs=[{"genes": [{"gene": "SYNTHETIC_GENE", "class": 1}], "size": 10, "ratio": 1}],
        translocs=[
            {"INFO": {"MANE_ANN": {"Gene_Name": "SYNTHETIC_A&SYNTHETIC_B", "HGVSp": "p.Synthetic"}}}
        ],
        hrd=[{"HRD": {"sum": 3, "tai": 1, "hrd": 1, "lst": 1}}],
        msi=[{"MSIS": {"per": 1, "som": 1, "tot": 100}}],
        tmb=[{"TMB": {"value": 1}}],
        biomarkers=[{"name": "Synthetic biomarker", "value": 1}],
        pgx=[{"gene": "SYNTHETIC_GENE", "result": "Synthetic phenotype"}],
    )
    outputs = {}
    for layout in ["legacy", "modern"]:
        output = render_report_html(
            template_name="dna_report.html",
            template_context=inputs,
            snapshot_rows=[],
            analyte="dna",
            preview=True,
            layout=layout,
        )
        root = HTML(string=output).etree_element
        tables = root.findall('.//table[@class="variant_table"]')
        assert len(tables) == 9
        assert not root.findall('.//p[@class="report-empty-result"]')
        outputs[layout] = [" ".join("".join(table.itertext()).split()) for table in tables]
    assert outputs["modern"] == outputs["legacy"]


def test_center_wording_is_optional_and_reloaded_without_aspc_edits(monkeypatch, tmp_path):
    monkeypatch.setattr(report_presentation, "CENTER_CONFIG_DIR", tmp_path)
    assert report_presentation.load_report_presentation() == ReportPresentation()
    config_file = tmp_path / "report_presentation.toml"
    config_file.write_text('[empty_results]\nCNV = "Synthetic CNV message"\n')
    settings = report_presentation.load_report_presentation()
    assert settings.empty_results.CNV == "Synthetic CNV message"
    assert settings.empty_results.SNV == ReportPresentation().empty_results.SNV
    inputs = empty_context()
    for message in ["First configured message", "Updated configured message"]:
        config_file.write_text(f'[empty_results]\nSNV = "{message}"\n')
        output = render_branded_report_html(
            config={},
            template_name="dna_report.html",
            template_context=inputs,
            snapshot_rows=[],
            analyte="dna",
            preview=True,
            layout="modern",
        )
        assert message in output

    inputs["report_presentation"] = {"empty_results": {"SNV": "Captured for reviewed render"}}
    output = render_branded_report_html(
        config={},
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    assert "Captured for reviewed render" in output
    assert "Updated configured message" not in output


@pytest.mark.parametrize(
    "content",
    [
        '[empty_results]\nSNVV = "Typo"',
        '[empty_results]\nSNV = "   "',
        "[empty_results]\nSNV = 12",
        "[empty_results",
    ],
)
def test_invalid_center_wording_fails_instead_of_silently_using_defaults(
    monkeypatch, tmp_path, content
):
    monkeypatch.setattr(report_presentation, "CENTER_CONFIG_DIR", tmp_path)
    (tmp_path / "report_presentation.toml").write_text(content)
    with pytest.raises((ValueError, ValidationError)):
        report_presentation.load_report_presentation()


def test_metadata_is_compact_in_a4_output_without_losing_fields():
    output = render_report_html(
        template_name="dna_report.html",
        template_context=empty_context(),
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
        organization_name="Synthetic institution",
        generated_by="Synthetic reviewer",
    )
    document = HTML(string=output).render()
    metadata = [
        box
        for page in document.pages
        for box in page._page_box.descendants()
        if box.element_tag == "section" and box.element.get("class") == "report-metadata"
    ]
    assert len(metadata) == 1
    assert metadata[0].height < 200
    metadata_element = HTML(string=output).etree_element.find(
        './/section[@class="report-metadata"]'
    )
    text = " ".join(metadata_element.itertext())
    for value in [
        "Patientnamn",
        "Personnummer",
        "SYNTHETIC_CASE",
        "SYNTHETIC_CONTROL",
        "Synthetic method",
        "Synthetic institution",
        "Synthetic reviewer",
        "SYNTHETIC_REPORT_ID",
    ]:
        assert value in text


def test_short_report_uses_compact_rows_and_keeps_details_with_the_summary():
    """Compact findings continue after the conclusion without a forced page break."""
    inputs = context()
    inputs["report_sections"] = ["SNV"]
    inputs["report_sections_data"] = {
        "snvs": [
            {
                "symbol": "SYNTHETIC_GENE",
                "variant": "p.Val1Ala",
                "cdna": "c.2T>C",
                "af": 0.42,
                "indel_size": 0,
                "class": 1,
                "class_short_desc": "Tier I",
                "class_long_desc": "Synthetic interpretation",
                "global_annotations": [],
                "annotations_interesting": {},
            }
        ]
    }
    inputs["latest_sample_comment_text"] = "SYNTHETIC_CONCLUSION"
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    html = HTML(string=output)
    document = html.render()
    first_page_text = " ".join(
        box.text for box in document.pages[0]._page_box.descendants() if isinstance(box, TextBox)
    )
    assert "SYNTHETIC_CONCLUSION" in first_page_text
    assert "Detekterade mutationer" in first_page_text
    table = html.etree_element.find('.//table[@class="variant_table"]')
    rows = set(table.findall(".//tr"))
    rendered_rows = [
        box
        for page in document.pages
        for box in page._page_box.descendants()
        if isinstance(box, TableRowBox) and box.element in rows
    ]
    assert len(rendered_rows) == 2
    assert all(row.height < 26 for row in rendered_rows)
