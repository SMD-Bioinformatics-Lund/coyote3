"""Registered templates retain deterministic hashes and HTML/PDF presentation."""

from copy import deepcopy

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
    "analyte,name", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_every_template_alias_uses_the_same_smd_renderer_and_identity(analyte, name):
    """Earlier identifiers select package-owned rendering without a filesystem fallback."""
    expected = template_content_hash(f"smd/{name}")
    for alias in (name, f"modern/{name}", f"smd/{name}"):
        assert select_report_template(alias, analyte) == (f"smd/{name}", "modern")
        assert template_content_hash(alias) == expected
        html = render_report_html(
            template_name=alias,
            template_context=context(),
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
        )
        assert 'name="smd-reports:package_version" content="0.5.3"' in html
        assert render_pdf_bytes(html).startswith(b"%PDF-")


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_legacy_layout_cannot_be_rendered(analyte):
    """Explicit requests for a removed layout fail instead of silently changing format."""
    with pytest.raises(ValueError, match="legacy layouts are not supported"):
        render_report_html(
            template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
            template_context=context(),
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
            layout="legacy",
        )


@pytest.mark.parametrize(
    "analyte,name", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_footer_template_version_is_independent_of_patient_report_number(analyte, name):
    """Repeated patient reports use the installed presentation version in the footer."""
    inputs = context()
    for number in (0, 8):
        inputs["sample"]["report_num"] = number
        html = render_report_html(
            template_name=name,
            template_context=inputs,
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
            layout="modern",
        )
        assert 'name="smd-reports:package_version" content="0.5.3"' in html
        assert 'name="smd-reports:template_version" content="0.5.3"' in html


@pytest.mark.parametrize(
    "analyte,name", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_approved_template_profile_selects_modern_without_changing_clinical_values(analyte, name):
    inputs = context()
    selected = f"smd/{name}"
    inputs["assay_config"]["template_release"] = {
        "template_name": selected,
        "content_hash": template_content_hash(selected),
    }
    html = render_report_html(
        template_name=name, template_context=inputs, snapshot_rows=[], analyte=analyte, preview=True
    )
    assert 'name="smd-reports:package_version" content="0.5.3"' in html
    assert "SYNTHETIC_EXTRACTION" in html
    issued = render_report_html(
        template_name=name,
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=False,
    )
    assert "TRY NEW REPORT · TEMPORARY PREVIEW" not in issued
    assert "@bottom-left { content: element(report-page-footer);" in issued
    assert 'name="smd-reports:template_version" content="0.5.3"' in issued
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
