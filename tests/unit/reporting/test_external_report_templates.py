"""External templates preserve approved legacy hashes, HTML and PDF presentation."""

from copy import deepcopy
from pathlib import Path

import pytest

from coyote3.application.reporting.report_renderer import (
    render_pdf_bytes,
    render_report_html,
    template_content_hash,
)
from coyote3.application.reporting.report_service import select_report_template
from coyote3.domain.exceptions import AppError


def context():
    """Return the synthetic inputs captured before extracting the embedded templates."""
    return {
        "sample": {"name": "SYNTHETIC_EXTRACTION", "case": {}, "control": {}},
        "assay_config": {"reporting": {"report_header": "Synthetic report"}},
        "report_header": "Synthetic report",
        "report_sections": [],
        "report_sections_data": {},
        "fusions": [],
        "genes_covered_in_panel": {},
    }


@pytest.mark.parametrize(
    "analyte,name,digest",
    [
        (
            "dna",
            "dna_report.html",
            "1081dbe2540a415b821366f524c1c5f3059782bddd91ad2b15166230771b5f62",
        ),
        (
            "rna",
            "report_fusion.html",
            "6f292583c7e8c4633707240bf776dc7ba97e1846f9af732ffe5c23b5bcc32f17",
        ),
    ],
)
@pytest.mark.parametrize("layout", ["legacy", "modern"])
def test_registered_layout_matches_html_fixture_and_preserves_legacy_digest(
    analyte, name, digest, layout
):
    inputs = context()
    original = deepcopy(inputs)
    html = render_report_html(
        template_name=name,
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout=layout,
    )
    expected = (
        (Path("tests/fixtures/report-templates") / f"{analyte}-{layout}.html")
        .read_text()
        .removesuffix("\n")
    )
    assert html == expected
    assert inputs == original
    assert template_content_hash(name) == digest
    pdf = render_pdf_bytes(html)
    assert pdf.startswith(b"%PDF-") and len(pdf) > 1000


@pytest.mark.parametrize(
    "analyte,name", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_approved_template_profile_selects_modern_without_changing_clinical_values(analyte, name):
    inputs = context()
    selected = f"modern/{name}"
    inputs["assay_config"]["template_release"] = {
        "template_name": selected,
        "content_hash": template_content_hash(selected),
    }
    html = render_report_html(
        template_name=name, template_context=inputs, snapshot_rows=[], analyte=analyte, preview=True
    )
    assert '<style id="modern-report-style">' in html
    assert "SYNTHETIC_EXTRACTION" in html
    issued = render_report_html(
        template_name=name,
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=False,
    )
    assert "TRY NEW REPORT · TEMPORARY PREVIEW" not in issued
    assert '@bottom-left { content: "Coyote3"; }' in issued
    inputs["assay_config"]["template_release"]["content_hash"] = "invalid"
    with pytest.raises(AppError, match="approved report template"):
        render_report_html(
            template_name=name,
            template_context=inputs,
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
        )


def test_registry_rejects_arbitrary_files_and_wrong_modality():
    with pytest.raises(ValueError, match="does not support"):
        select_report_template("../../private.html", "dna")
    with pytest.raises(ValueError, match="does not support"):
        select_report_template("modern/report_fusion.html", "dna")


def test_render_context_prepares_selected_calls_without_mutating_clinical_input():
    """Templates receive preselected calls in their existing order and retain all finding rows."""
    from coyote3.application.reporting.report_context import prepare_render_context

    inputs = context()
    inputs["fusions"] = [
        {
            "calls": [
                {"selected": 0, "spanreads": 10},
                {"selected": 1, "spanreads": 25},
                {"selected": True, "spanreads": 30},
            ]
        }
    ]
    original = deepcopy(inputs)
    prepared = prepare_render_context(inputs, analyte="rna", preview=True)
    assert prepared["fusions"][0]["report_selected_calls"] == inputs["fusions"][0]["calls"][1:]
    assert len(prepared["fusions"]) == len(inputs["fusions"])
    assert inputs == original
