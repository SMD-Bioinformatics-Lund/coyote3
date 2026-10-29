"""Modern A4 reports retain long clinical text and images within printable page bounds."""

import base64
import re
from io import BytesIO

import pytest
from PIL import Image
from weasyprint import CSS, HTML
from weasyprint.formatting_structure.boxes import MarginBox, ReplacedBox, TextBox

from coyote3.application.reporting.report_renderer import render_report_html
from coyote3.application.reporting.report_service import modern_template_version


def pagination_context(analyte, image_shape):
    """Prepare synthetic long annotations, identifiers and optional CNV profile images."""
    notes = "\n\n".join(
        f"SYNTHETIC_NOTE_{index:03d} Clinical interpretation text for pagination validation. "
        "This synthetic paragraph must remain readable and present in the downloaded report."
        for index in range(90)
    )
    variant = {
        "symbol": "SYNTHETIC_GENE",
        "variant": "c.123_124ins" + "ACGT" * 80,
        "cdna": "c.123_124ins" + "ACGT" * 80,
        "af": 0.25,
        "indel_size": 320,
        "class": 1,
        "class_short_desc": "Tier I",
        "class_long_desc": "Synthetic classification",
        "global_annotations": [{"text": notes, "time_created": 1}],
        "annotations_interesting": {},
    }
    context = {
        "sample": {"name": "SYNTHETIC_PAGINATION", "case_id": "SYNTHETIC-" * 30},
        "assay_config": {
            "reporting": {
                "report_header": "Synthetic report",
                "report_method": "Synthetic assay",
            }
        },
        "report_header": "Synthetic report",
        "clinical_rule_evaluation": {
            "sections": {"analysis_description": ["SYNTHETIC_DESCRIPTION_END"]}
        },
        "report_sections": ["SNV"] if analyte == "dna" else [],
        "report_sections_data": {"snvs": [variant]},
        "genes_covered_in_panel": {},
        "class_desc": {1: "Synthetic classification"},
        "class_desc_short": {1: "Tier I"},
        "fusions": [
            {
                "gene1": "SYNTHETIC_GENE_A",
                "gene2": "SYNTHETIC_GENE_B",
                "classification": {"class": 1},
                "calls": [{"selected": 1, "spanpairs": 20, "spanreads": 30}],
                "global_annotations": [{"text": notes, "time_created": 1}],
            }
        ],
    }
    if image_shape:
        image = Image.new("RGB", image_shape, "#dce4e8")
        stream = BytesIO()
        image.save(stream, format="PNG")
        context["report_sections_data"]["cnv_profile_base64"] = base64.b64encode(
            stream.getvalue()
        ).decode()
    return context


@pytest.mark.parametrize(
    "analyte,image_shape", [("dna", (1600, 300)), ("dna", (400, 1600)), ("rna", None)]
)
def test_modern_report_content_fits_a4_and_keeps_long_annotation_tail(analyte, image_shape):
    """Long notes fragment across pages without losing text or exceeding print margins."""
    html = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=pagination_context(analyte, image_shape),
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
    )
    document = HTML(string=html).render()
    assert len(document.pages) > 2
    text = []
    for page in document.pages:
        visible = []
        bounds = page._page_box
        left, top = bounds.content_box_x(), bounds.content_box_y()
        right, bottom = left + bounds.width, top + bounds.height
        margin_boxes = {
            id(box)
            for child in bounds.children
            if isinstance(child, MarginBox)
            for box in child.descendants()
        }
        assert page.width == pytest.approx(210 * 96 / 25.4)
        assert page.height == pytest.approx(297 * 96 / 25.4)
        for box in bounds.descendants():
            if box.element_tag is None or not isinstance(box, (TextBox, ReplacedBox)):
                continue
            assert box.position_x >= left - 1
            assert box.position_x + box.width <= right + 1
            if id(box) in margin_boxes:
                assert box.position_y >= 0
                assert box.position_y + box.height <= page.height
            else:
                visible.append(box)
                assert box.position_y >= top - 1
                assert box.position_y + box.height <= bottom + 1
            if isinstance(box, TextBox):
                text.append(box.text)
        assert visible, "A report page contains only headers or footers"
    rendered_text = " ".join(text)
    assert "SYNTHETIC_NOTE_000" in rendered_text
    assert "SYNTHETIC_NOTE_089" in rendered_text
    assert "SYNTHETIC_DESCRIPTION_END" in rendered_text


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_screen_and_pdf_share_content_width_and_keep_all_patient_fields(analyte):
    """The compact repeating PDF header keeps all fields within the shared paper width."""
    html = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=pagination_context(analyte, None),
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
        organization_name="Section For Molecular Diagnostics (SMD)",
    )
    # A wide, tall viewport lets the screen stylesheet lay out a continuous paper sheet.
    screen = HTML(string=html, media_type="screen").render(
        stylesheets=[CSS(string="@page { size: 250mm 2000mm; margin: 0; }")]
    )
    pdf = HTML(string=html).render()
    for class_name in [
        "report-content",
        "report-metadata",
        "report-patient-table",
        "variant_table",
        "report_variant",
    ]:
        boxes = []
        for document in (screen, pdf):
            boxes.append(
                next(
                    box
                    for page in document.pages
                    for box in page._page_box.descendants()
                    if box.element is not None and box.element.get("class") == class_name
                )
            )
        assert boxes[0].width == pytest.approx(boxes[1].width, abs=0.1), class_name
        if class_name == "report-content":
            assert boxes[0].width == pytest.approx(178 * 96 / 25.4, abs=0.1)
        if class_name == "report-metadata":
            assert boxes[1].height < boxes[0].height
            lines = [
                [box.text for box in metadata.descendants() if isinstance(box, TextBox)]
                for metadata in boxes
            ]
            assert re.sub(r"\s+", "", "".join(lines[0])) == re.sub(r"\s+", "", "".join(lines[1]))


def test_long_result_table_repeats_column_headings_without_losing_findings():
    """Each continuation page identifies its columns and retains every finding once."""
    inputs = pagination_context("dna", None)
    variant = {
        **inputs["report_sections_data"]["snvs"][0],
        "variant": "p.Synthetic",
        "cdna": "c.Synthetic",
        "indel_size": 0,
        "class": 999,
        "global_annotations": [],
    }
    inputs["report_sections_data"]["snvs"] = [
        {**variant, "symbol": f"SYNTHETIC_{index:03d}"} for index in range(100)
    ]
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    # Isolate the rendered summary table so detail sections do not repeat finding names.
    table = re.search(
        r'<table class="variant_table" data-analysis="snv">.*?</table>', html, re.S
    ).group()
    document = HTML(
        string=html.partition("<body>")[0]
        + '<body><div class="page">'
        + table
        + "</div></body></html>"
    ).render()
    assert len(document.pages) > 1
    findings = []
    for page in document.pages:
        words = [box.text for box in page._page_box.descendants() if isinstance(box, TextBox)]
        for label in ["Gen", "Mutation", "Variantfrekvens", "Klassificering"]:
            assert label in words
        findings.extend(word for word in words if word.startswith("SYNTHETIC_"))
    assert findings == [f"SYNTHETIC_{index:03d}" for index in range(100)]


def test_short_variant_details_stay_on_one_page_and_footer_identifies_template_version():
    """Compact details move intact; every page identifies the installed template version."""
    inputs = pagination_context("dna", None)
    variant = {
        **inputs["report_sections_data"]["snvs"][0],
        "variant": "p.Synthetic",
        "cdna": "c.Synthetic",
        "indel_size": 0,
        "global_annotations": [],
    }
    inputs["sample"]["report_num"] = 3
    inputs["report_sections_data"]["snvs"] = [
        {**variant, "symbol": f"DETAIL_{index:03d}"} for index in range(30)
    ]
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    document = HTML(string=html).render()
    table_pages = {}
    for index, page in enumerate(document.pages):
        words = [box.text for box in page._page_box.descendants() if isinstance(box, TextBox)]
        assert f"DNA template v{modern_template_version('dna')}" in words
        for box in page._page_box.descendants():
            if box.element is not None and box.element.get("class") == "report_variant":
                table_pages.setdefault(box.element, set()).add(index)
    assert len(table_pages) == 30
    assert all(len(pages) == 1 for pages in table_pages.values())
