"""Modern report logos are embedded, center-configurable and safe for offline rendering."""

from base64 import b64encode

import pytest
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import ReplacedBox, TextBox

from api.presentation.reports import branding
from coyote3.application.reporting.pdf_resources import ReportResourceFetcher, validate_report_svg
from coyote3.application.reporting.report_renderer import render_pdf_bytes


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


@pytest.mark.parametrize(
    "template_name,layout", [("dna_report.html", "modern"), ("modern/dna_report.html", None)]
)
def test_modern_header_embeds_both_logos_and_renders_metadata_cards_and_pdf(template_name, layout):
    html = branding.render_branded_report_html(
        config={},
        layout=layout,
        organization_name="SYNTHETIC CENTER",
        generated_by="Synthetic reviewer",
        template_name=template_name,
        analyte="dna",
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
    assert html.count('src="data:image/svg+xml;base64,') == 2
    assert 'class="report-metadata"' in html and "<dl>" in html
    assert "SYNTHETIC_CASE" in html and "SYNTHETIC CENTER" in html
    assert "Synthetic reviewer" in html
    document = HTML(string=html).render()
    assert len(document.pages) <= 2
    for page in document.pages:
        bounds = page._page_box
        for box in bounds.descendants():
            if box.element_tag is None or not isinstance(box, (ReplacedBox, TextBox)):
                continue
            assert box.position_x >= bounds.content_box_x() - 1
            assert box.position_x + box.width <= bounds.content_box_x() + bounds.width + 1
            assert box.position_y >= bounds.content_box_y() - 1
            assert box.position_y + box.height <= bounds.content_box_y() + bounds.height + 1
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
