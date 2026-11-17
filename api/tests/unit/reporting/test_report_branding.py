"""Modern report logos are embedded, center-configurable and safe for offline rendering."""

import re
from base64 import b64encode
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree

import pytest
from api_test_support.report_context import context
from coyote.application.reporting.pdf_resources import ReportResourceFetcher
from coyote.application.reporting.report_renderer import render_pdf_bytes, render_report_html
from coyote_api.presentation.reports import branding
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import ReplacedBox, TextBox


def test_bundled_branding_contains_both_embedded_vector_logos():
    logos = branding.load_report_branding({})
    assert set(logos) == {"coyote_logo", "center_logo"}
    for url in logos.values():
        assert url.startswith("data:image/svg+xml;base64,")
        resource = ReportResourceFetcher()(url)
        try:
            assert ElementTree.fromstring(resource.read()).tag == "{http://www.w3.org/2000/svg}svg"
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
@pytest.mark.parametrize("logo_kind", ["font-embedded", "static"])
def test_accreditation_is_printed_only_for_true_in_the_applied_assay(
    accredited, analyte, logo_kind, tmp_path, monkeypatch
):
    """Only the captured assay accreditation enables the optional footer logo on every page."""
    from api_test_support.report_presentation import empty_context

    monkeypatch.setattr(branding, "CENTER_CONFIG_DIR", tmp_path)
    artwork = Path(
        str(
            files("coyote_api").joinpath(
                "config/examples/center/logos/swedac-iso-15189-example.svg"
            )
        )
    ).read_bytes()
    if logo_kind == "static":
        artwork = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="28" '
            b'viewBox="0 0 24 28"><rect width="24" height="28" fill="#ddd"/></svg>'
        )
    (tmp_path / "accreditation.svg").write_bytes(artwork)
    inputs = empty_context()
    inputs["assay_config"]["assay_resource_release"] = {"content": {"accredited": accredited}}
    html = branding.render_branded_report_html(
        config={"CONTACT": {"organization": {"accreditation_logo": "accreditation.svg"}}},
        template_name="dna" if analyte == "dna" else "rna",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=False,
    )
    assert ('<img class="accreditation"' in html) is (accredited is True)
    document = HTML(string=html).render()
    for index, page in enumerate(document.pages, 1):
        boxes = list(page._page_box.descendants())
        logos = [
            box
            for box in boxes
            if isinstance(box, ReplacedBox) and box.element.get("class") == "accreditation"
        ]
        assert len(logos) == int(accredited is True)
        assert page._page_box.margin_bottom == pytest.approx(
            (38 if accredited is True else 22) * 96 / 25.4
        )
        text = " ".join(box.text for box in boxes if isinstance(box, TextBox))
        assert ("SYNTHETIC_CASE" if analyte == "dna" else inputs["sample"]["name"]) in text
        assert f"Sida {index} av {len(document.pages)}" in text
        # The installed package owns the template identity independently of app branding.
        assert f"Coyote3 {analyte.upper()} · Template 0.5.3" in text
        version = next(
            box
            for box in boxes
            if isinstance(box, TextBox) and box.text.startswith(f"Coyote3 {analyte.upper()}")
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
            # Fit the reserved footer while preserving the supplied artwork's aspect ratio.
            assert logo.height <= 29 * 96 / 25.4 + 0.01
            assert logo.width <= 25 * 96 / 25.4 + 0.01
            assert logo.width > 0 and logo.height > 0
            assert logo.style["object_fit"] == "contain"
            _, _, intrinsic_ratio = logo.replacement.get_intrinsic_size(
                logo.style["image_resolution"], logo.style["font_size"]
            )
            assert intrinsic_ratio == pytest.approx(24 / 28)
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
    "template_name,analyte",
    [
        ("dna", "dna"),
        ("rna", "rna"),
    ],
)
def test_modern_header_embeds_both_logos_and_renders_metadata_cards_and_pdf(template_name, analyte):
    html = branding.render_branded_report_html(
        config={},
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
    wordmark = HTML(string=html).etree_element.find('.//strong[@class="application-name"]')
    assert "".join(wordmark.itertext()) == "Coyote4"
    document = HTML(string=html).render()
    assert len(document.pages) == 3  # Results, isolated conclusion, and analysis description.
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
        if isinstance(box, ReplacedBox) and box.element.get("class") == "report-application-logo"
    )
    title = next(
        box
        for box in first_page.descendants()
        if box.element is not None and box.element.get("class") == "application-name"
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


def test_default_rendering_validates_branding_without_a_legacy_fallback():
    """The default renderer must not bypass missing configured artwork."""
    with pytest.raises((ValueError, FileNotFoundError)):
        branding.render_branded_report_html(
            config={"CONTACT": {"organization": {"report_logo": "missing.svg"}}},
            template_name="dna",
            analyte="dna",
            preview=True,
            snapshot_rows=[],
            template_context=context(),
        )


def test_center_contact_details_are_optional_and_escaped_in_modern_header():
    """Configured address appears in the header while phone remains outside the report."""
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
        template_name="dna",
        analyte="dna",
        preview=True,
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
    assert "+46 00 123456" not in html
    assert 'class="report-center-phone"' not in html
    assert render_pdf_bytes(html).startswith(b"%PDF-")
    absent = branding.load_report_branding({})
    assert "center_address" not in absent and "center_phone" not in absent


def test_self_contained_svg_font_is_preserved_and_embedded_in_pdf(tmp_path, monkeypatch):
    """Supplied logo-style WOFF2 text renders offline without rewriting the SVG."""
    fonts_css = render_report_html(
        template_name="dna",
        template_context=context(),
        snapshot_rows=[],
        analyte="dna",
        preview=True,
    )
    font_url = re.search(r"data:font/woff2;base64,[A-Za-z0-9+/=]+", fonts_css).group()
    artwork = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="184" height="209" '
        'viewBox="0 0 184 209"><defs><style>'
        "@font-face {font-family: 'SyntheticLogo'; src: url('" + font_url + "');}"
        '</style></defs><text x="5" y="100" font-family="SyntheticLogo" '
        'font-size="18">Synthetic accreditation</text></svg>'
    ).encode()
    (tmp_path / "logo.svg").write_bytes(artwork)
    monkeypatch.setattr(branding, "CENTER_CONFIG_DIR", tmp_path)
    logos = branding.load_report_branding(
        {"CONTACT": {"organization": {"accreditation_logo": "logo.svg"}}}
    )
    expected = "data:image/svg+xml;base64," + b64encode(artwork).decode()
    assert logos["accreditation_logo"] == expected
    html = f'<html><body><img src="{expected}"></body></html>'
    document = HTML(string=html, url_fetcher=ReportResourceFetcher()).render()
    assert document.write_pdf().startswith(b"%PDF-")
    assert "SyntheticLogo" in {font.family for font in document.fonts.values()}
