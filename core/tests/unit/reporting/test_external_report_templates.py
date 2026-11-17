"""Registered templates retain deterministic hashes and HTML/PDF presentation."""

from copy import deepcopy

import pytest
from core_test_support.report_context import context
from coyote.application.reporting.report_renderer import (
    render_pdf_bytes,
    render_report_html,
)
from coyote.application.reporting.report_service import (
    select_report_template,
    template_content_hash,
)
from coyote.domain.exceptions import AppError


@pytest.mark.parametrize("analyte,name", [("dna", "dna"), ("rna", "rna")])
def test_canonical_templates_render_and_retired_aliases_are_rejected(analyte, name):
    """Only the registered package identifiers select report rendering."""
    assert select_report_template(name, analyte) == name
    assert template_content_hash(name)
    html = render_report_html(
        template_name=name,
        template_context=context(),
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
    )
    assert 'name="smd-reports:package_version" content="0.5.3"' in html
    assert render_pdf_bytes(html).startswith(b"%PDF-")
    for alias in (
        "smd/dna_report.html",
        "smd/report_fusion.html",
        "dna_report.html",
        "report_fusion.html",
    ):
        with pytest.raises(ValueError):
            select_report_template(alias, analyte)


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_legacy_layout_cannot_be_rendered(analyte):
    """Explicit requests for a removed layout fail instead of silently changing format."""
    with pytest.raises(TypeError, match="layout"):
        render_report_html(
            template_name="dna" if analyte == "dna" else "rna",
            template_context=context(),
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
            layout="legacy",
        )


@pytest.mark.parametrize("analyte,name", [("dna", "dna"), ("rna", "rna")])
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
        )
        assert 'name="smd-reports:package_version" content="0.5.3"' in html
        assert 'name="smd-reports:template_version" content="0.5.3"' in html


@pytest.mark.parametrize("analyte,name", [("dna", "dna"), ("rna", "rna")])
def test_approved_template_profile_selects_modern_without_changing_clinical_values(analyte, name):
    inputs = context()
    selected = name
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
        select_report_template("rna", "dna")


def test_render_context_prepares_selected_calls_without_mutating_clinical_input():
    """Templates receive preselected calls in their existing order and retain all finding rows."""
    from coyote.application.reporting.report_context import prepare_render_context

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
