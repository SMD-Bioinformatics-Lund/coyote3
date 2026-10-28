"""Modern report logos are embedded, center-configurable and safe for offline rendering."""

import re
from base64 import b64encode
from pathlib import Path

import pytest
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import ReplacedBox, TextBox

from api.presentation.reports import branding
from coyote3.application.reporting.pdf_resources import ReportResourceFetcher, validate_report_svg
from coyote3.application.reporting.report_renderer import render_pdf_bytes, render_report_html


def test_bundled_branding_contains_both_embedded_vector_logos():
    logos = branding.load_report_branding({})
    assert set(logos) == {"coyote_logo", "center_logo"}
    for url in logos.values():
        assert url.startswith("data:image/svg+xml;base64,")
        resource = ReportResourceFetcher()(url)
        try:
            assert b"<svg" in resource.read()
        finally:
            resource.close()


def test_center_can_select_a_local_logo_or_omit_it(tmp_path, monkeypatch):
    monkeypatch.setattr(branding, "CENTER_CONFIG_DIR", tmp_path)
    (tmp_path / "center.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h5v5Z"/></svg>'
    )
    assert "center_logo" in branding.load_report_branding(
        {"CONTACT": {"organization": {"report_logo": "center.svg"}}}
    )
    assert set(
        branding.load_report_branding({"CONTACT": {"organization": {"report_logo": ""}}})
    ) == {"coyote_logo"}
    with pytest.raises(ValueError, match="inside the center"):
        branding.load_report_branding(
            {"CONTACT": {"organization": {"report_logo": "../private.svg"}}}
        )


@pytest.mark.parametrize("accredited", [True, False, None, "true"])
@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_accreditation_is_printed_only_for_true_in_the_applied_assay(
    accredited, analyte, tmp_path, monkeypatch
):
    """Only the captured assay accreditation enables the optional footer logo on every page."""
    from tests.unit.reporting.test_report_presentation import empty_context

    monkeypatch.setattr(branding, "CENTER_CONFIG_DIR", tmp_path)
    (tmp_path / "accreditation.svg").write_bytes(
        Path("config/examples/center/logos/swedac-iso-15189-example.svg").read_bytes()
    )
    inputs = empty_context()
    inputs["assay_config"]["assay_resource_release"] = {"content": {"accredited": accredited}}
    html = branding.render_branded_report_html(
        config={"CONTACT": {"organization": {"accreditation_logo": "accreditation.svg"}}},
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=False,
        layout="modern",
    )
    assert ('<img class="report-accreditation-logo"' in html) is (accredited is True)
    document = HTML(string=html).render()
    for index, page in enumerate(document.pages, 1):
        boxes = list(page._page_box.descendants())
        logos = [
            box
            for box in boxes
            if isinstance(box, ReplacedBox)
            and box.element.get("class") == "report-accreditation-logo"
        ]
        assert len(logos) == int(accredited is True)
        assert page._page_box.margin_bottom == pytest.approx(
            (38 if accredited is True else 22) * 96 / 25.4
        )
        text = " ".join(box.text for box in boxes if isinstance(box, TextBox))
        assert ("SYNTHETIC_CASE" if analyte == "dna" else inputs["sample"]["name"]) in text
        assert f"Sida {index} av {len(document.pages)}" in text
        assert f"{analyte.upper()} template v" in text
        version = next(
            box
            for box in boxes
            if isinstance(box, TextBox) and box.text.startswith(f"{analyte.upper()} template v")
        )
        page_number = next(
            box for box in boxes if isinstance(box, TextBox) and box.text.startswith("Sida ")
        )
        assert version.position_y >= page._page_box.content_box_y() + page._page_box.height
        assert version.position_y + version.height <= page_number.position_y
        assert page_number.position_y + page_number.height <= page.height
        content_right = page._page_box.content_box_x() + page._page_box.width
        assert version.position_x + version.width == pytest.approx(content_right, abs=1)
        assert page_number.position_x + page_number.width == pytest.approx(content_right, abs=1)
        assert page.height - (page_number.position_y + page_number.height) >= 8 * 96 / 25.4
        for logo in logos:
            assert logo.height == pytest.approx(28 * 96 / 25.4)
            assert logo.width == pytest.approx(24 * 96 / 25.4)
            assert logo.position_y >= page._page_box.content_box_y() + page._page_box.height
            assert page.height - (logo.position_y + logo.height) >= 5 * 96 / 25.4
            assert logo.position_x == pytest.approx(page._page_box.content_box_x(), abs=1)
            assert logo.position_x + logo.width < version.position_x
        header = next(
            box
            for box in boxes
            if box.element is not None and box.element.get("class") == "report-page-header"
        )
        assert header.position_y >= 0
        assert header.position_y + header.height <= page._page_box.content_box_y() + 1
    with pytest.raises(ValueError, match="inside the center"):
        branding.load_report_branding(
            {"CONTACT": {"organization": {"accreditation_logo": "../outside.svg"}}}
        )


@pytest.mark.parametrize(
    "template_name,layout,analyte",
    [
        ("dna_report.html", "modern", "dna"),
        ("modern/dna_report.html", None, "dna"),
        ("report_fusion.html", "modern", "rna"),
        ("modern/report_fusion.html", None, "rna"),
    ],
)
def test_modern_header_embeds_both_logos_and_renders_metadata_cards_and_pdf(
    template_name, layout, analyte
):
    html = branding.render_branded_report_html(
        config={},
        layout=layout,
        organization_name="SYNTHETIC CENTER",
        generated_by="Synthetic reviewer",
        template_name=template_name,
        analyte=analyte,
        preview=True,
        snapshot_rows=[],
        template_context={
            "sample": {"name": "SYNTHETIC_REPORT", "case_id": "SYNTHETIC_CASE"},
            "assay_config": {"reporting": {"report_header": "Synthetic report"}},
            "report_sections": [],
            "report_sections_data": {},
            "genes_covered_in_panel": {},
        },
    )
    assert html.count('src="data:image/svg+xml;base64,') == 4
    assert 'class="report-metadata"' in html and '<table class="report-patient-table"' in html
    assert ("SYNTHETIC_CASE" if analyte == "dna" else "SYNTHETIC_REPORT") in html
    assert "SYNTHETIC CENTER" in html
    assert "Synthetic reviewer" in html
    document = HTML(string=html).render()
    assert len(document.pages) <= 2
    first_page = document.pages[0]._page_box
    center = next(
        box
        for box in first_page.descendants()
        if box.element is not None and box.element.get("class") == "report-center-brand"
    )
    logo = next(box for box in center.descendants() if isinstance(box, ReplacedBox))
    coyote = next(
        box
        for box in first_page.descendants()
        if isinstance(box, ReplacedBox) and box.element.get("class") == "report-coyote-logo"
    )
    title = next(
        box
        for box in first_page.descendants()
        if isinstance(box, TextBox) and box.text == "COYOTE3"
    )
    assert logo.height == pytest.approx(coyote.height)
    assert 0 <= title.position_x - (coyote.border_box_x() + coyote.width) <= 12
    center_name = [box for box in center.descendants() if isinstance(box, TextBox)]
    assert logo.border_box_x() + logo.width == pytest.approx(
        first_page.content_box_x() + first_page.width, abs=1
    )
    assert center_name
    assert all(box.style["font_size"] <= 7 * 96 / 72 + 0.01 for box in center_name)
    assert max(box.position_x + box.width for box in center_name) <= logo.border_box_x() - 1
    assert min(box.position_y for box in center_name) >= center.position_y
    for page in document.pages:
        bounds = page._page_box
        for box in bounds.descendants():
            if box.element_tag is None or not isinstance(box, (ReplacedBox, TextBox)):
                continue
            assert box.position_x >= bounds.content_box_x() - 1
            assert box.position_x + box.width <= bounds.content_box_x() + bounds.width + 1
            # Running header/footer content occupies the reserved page margins.
            assert box.position_y >= 0
            assert box.position_y + box.height <= bounds.margin_height() + 1
    assert render_pdf_bytes(html).startswith(b"%PDF-")


def test_legacy_rendering_does_not_require_modern_branding():
    html = branding.render_branded_report_html(
        config={"CONTACT": {"organization": {"report_logo": "missing.svg"}}},
        template_name="dna_report.html",
        analyte="dna",
        preview=True,
        snapshot_rows=[],
        template_context={
            "sample": {"name": "SYNTHETIC_REPORT", "case": {}, "control": {}},
            "assay_config": {"reporting": {"report_header": "Synthetic report"}},
            "report_sections": [],
            "report_sections_data": {},
            "genes_covered_in_panel": {},
        },
    )
    assert "SYNTHETIC_REPORT" in html
    assert 'src="data:image/svg+xml' not in html


def test_center_contact_details_are_optional_and_escaped_in_modern_header():
    """Only configured center address and telephone appear alongside the identity."""
    config = {
        "CONTACT": {
            "organization": {
                "address": "Synthetic Road 1\n12345 Example <center>",
                "phone": "+46 00 123456",
            }
        }
    }
    html = branding.render_branded_report_html(
        config=config,
        template_name="dna_report.html",
        analyte="dna",
        preview=True,
        layout="modern",
        template_context={
            "sample": {"name": "SYNTHETIC_CONTACT"},
            "assay_config": {"reporting": {"report_header": "Synthetic report"}},
            "report_sections": [],
            "report_sections_data": {},
            "genes_covered_in_panel": {},
        },
        snapshot_rows=[],
    )
    assert "12345 Example &lt;center&gt;" in html
    assert "+46 00 123456" in html
    assert 'class="report-center-phone"' in html
    assert render_pdf_bytes(html).startswith(b"%PDF-")
    absent = branding.load_report_branding({})
    assert "center_address" not in absent and "center_phone" not in absent


def test_modern_pdf_embeds_regular_semibold_and_italic_without_system_font_fallback():
    """PDF text uses the packaged font for Swedish text, labels and authored emphasis."""
    html = render_report_html(
        template_name="dna_report.html",
        analyte="dna",
        preview=True,
        layout="modern",
        snapshot_rows=[],
        template_context={
            "sample": {"name": "SYNTHETIC_TYPOGRAPHY"},
            "assay_config": {"reporting": {"report_header": "Syntetisk analysrapport"}},
            "report_sections": [],
            "report_sections_data": {},
            "genes_covered_in_panel": {},
            "latest_sample_comment_text": "Åäö **Syntetiskt fynd** och *syntetisk tolkning*.",
        },
    )
    fonts = re.findall(r"data:font/woff2;base64,[A-Za-z0-9+/=]+", html)
    assert len(fonts) == 3
    for url in fonts:
        resource = ReportResourceFetcher()(url)
        try:
            assert resource.read().startswith(b"wOF2")
        finally:
            resource.close()
    document = HTML(string=html, url_fetcher=ReportResourceFetcher()).render()
    assert document.write_pdf().startswith(b"%PDF-")
    assert {font.family for font in document.fonts.values()} == {"Source Sans 3"}
    assert {font.weight for font in document.fonts.values()} == {400, 600}
    assert any(font.style for font in document.fonts.values())


@pytest.mark.parametrize("content", [b"not a font", b"<script>unsafe</script>"])
def test_report_font_resource_rejects_content_without_woff2_signature(content):
    """The font allowlist does not admit another embedded resource type."""
    with pytest.raises(ValueError, match="must be WOFF2"):
        ReportResourceFetcher()("data:font/woff2;base64," + b64encode(content).decode())


@pytest.mark.parametrize(
    "body",
    [
        "<script>alert(1)</script>",
        '<image href="https://example.invalid/image.png"/>',
        '<use href="file:///private.svg"/>',
        '<path onload="alert(1)"/>',
        '<style>@import "https://example.invalid/style.css";</style>',
        '<path style="fill:url(https://example.invalid/image.svg)"/>',
        "<foreignObject><div>content</div></foreignObject>",
    ],
)
def test_svg_logo_rejects_active_content_and_external_resources(body):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'.encode()
    with pytest.raises(ValueError):
        validate_report_svg(svg)
    with pytest.raises(ValueError):
        ReportResourceFetcher()("data:image/svg+xml;base64," + b64encode(svg).decode())
