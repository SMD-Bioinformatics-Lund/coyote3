"""Modern A4 reports retain long clinical text and images within printable page bounds."""

import base64
from io import BytesIO

import pytest
from PIL import Image
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import ReplacedBox, TextBox

from coyote3.application.reporting.report_renderer import render_report_html


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
                "report_description": "<p>SYNTHETIC_DESCRIPTION_END</p>",
            }
        },
        "report_header": "Synthetic report",
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
        assert page.width == pytest.approx(210 * 96 / 25.4)
        assert page.height == pytest.approx(297 * 96 / 25.4)
        for box in bounds.descendants():
            if box.element_tag is None or not isinstance(box, (TextBox, ReplacedBox)):
                continue
            visible.append(box)
            assert box.position_x >= left - 1
            assert box.position_x + box.width <= right + 1
            assert box.position_y >= top - 1
            assert box.position_y + box.height <= bottom + 1
            if isinstance(box, TextBox):
                text.append(box.text)
        assert visible, "A report page contains only headers or footers"
    rendered_text = " ".join(text)
    assert "SYNTHETIC_NOTE_000" in rendered_text
    assert "SYNTHETIC_NOTE_089" in rendered_text
    assert "SYNTHETIC_DESCRIPTION_END" in rendered_text
