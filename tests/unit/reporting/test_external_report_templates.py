"""External templates preserve approved legacy hashes, HTML and PDF presentation."""

from copy import deepcopy
from pathlib import Path
from tomllib import TOMLDecodeError

import pytest
from pydantic import ValidationError

from coyote3.application.reporting import report_service
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


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_template_version_participates_in_its_analyte_identity_only(monkeypatch, analyte):
    """Releasing one analyte changes only its versioned identity and header label."""
    names = {"dna": "dna_report.html", "rna": "report_fusion.html"}
    hashes = {name: template_content_hash(name) for name in report_service.REPORT_TEMPLATES}
    versions = {key: report_service.modern_template_version(key) for key in names}
    versions[analyte] = "1.99.0"
    source = "\n".join(f'[{key}]\nversion = "{value}"' for key, value in versions.items())
    original_source = report_service._expanded_source
    monkeypatch.setattr(
        report_service,
        "_expanded_source",
        lambda name: source if name == "modern/manifest.toml" else original_source(name),
    )
    for modality, name in names.items():
        assert report_service.modern_template_version(modality) == versions[modality]
        assert template_content_hash(name) == hashes[name]
        assert (template_content_hash(f"modern/{name}") != hashes[f"modern/{name}"]) == (
            modality == analyte
        )
        html = render_report_html(
            template_name=name,
            template_context=context(),
            snapshot_rows=[],
            analyte=modality,
            preview=True,
            layout="modern",
        )
        assert (
            f'class="report-template-version">{modality.upper()} template v{versions[modality]}</span>'
            in html
        )


@pytest.mark.parametrize(
    "source",
    [
        "",
        '[dna]\nversion = "1.0.0"',
        '[dna]\nversion = "1.0"\n[rna]\nversion = "1.0.0"',
        '[dna]\nversion = 1\n[rna]\nversion = "1.0.0"',
        '[dna]\nversion = "01.0.0"\n[rna]\nversion = "1.0.0"',
        '[dna]\nversion = "1.0.0"\nunknown = true\n[rna]\nversion = "1.0.0"',
        "not valid TOML",
    ],
)
def test_template_manifest_rejects_invalid_metadata_without_a_default(monkeypatch, source):
    """A missing or invalid version cannot silently label a report with a fallback release."""
    monkeypatch.setattr(report_service, "_expanded_source", lambda name: source)
    with pytest.raises((ValidationError, TOMLDecodeError)):
        report_service.modern_template_version("dna")


def test_template_version_rejects_unsupported_analyte():
    """An unsupported modality cannot silently receive another report's template version."""
    with pytest.raises(ValueError, match="DNA or RNA"):
        report_service.modern_template_version("protein")


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
        version = report_service.modern_template_version(analyte)
        assert (
            f'class="report-template-version">{analyte.upper()} template v{version}</span>' in html
        )


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
    assert "@bottom-left { content: element(report-page-footer); }" in issued
    version = report_service.modern_template_version(analyte)
    assert f'class="report-template-version">{analyte.upper()} template v{version}</span>' in issued
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
