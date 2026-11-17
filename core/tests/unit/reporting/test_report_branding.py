"""Modern report logos are embedded, center-configurable and safe for offline rendering."""

import re
from base64 import b64encode

import pytest
from coyote.application.reporting.pdf_resources import ReportResourceFetcher, validate_report_svg
from coyote.application.reporting.report_renderer import render_report_html
from weasyprint import HTML


def test_modern_pdf_embeds_authored_emphasis_without_system_font_fallback():
    """PDF text uses the packaged font for Swedish text, labels and authored emphasis."""
    html = render_report_html(
        template_name="dna",
        analyte="dna",
        preview=True,
        snapshot_rows=[],
        template_context={
            "sample": {"name": "SYNTHETIC_TYPOGRAPHY"},
            "assay_config": {"reporting": {"report_header": "Syntetisk analysrapport"}},
            "report_sections": [],
            "report_sections_data": {},
            "genes_covered_in_panel": {},
            "latest_sample_comment_text": (
                "Åäö **Syntetiskt fynd** och *syntetisk tolkning*, med ***betonad tolkning***."
            ),
        },
    )
    fonts = re.findall(r"data:font/woff2;base64,[A-Za-z0-9+/=]+", html)
    assert len(fonts) == 6
    faces = re.findall(r"@font-face\s*\{([^}]+)\}", html)
    styles = {
        (
            int(re.search(r"font-weight:\s*(\d+)", face).group(1)),
            re.search(r"font-style:\s*(\w+)", face).group(1),
        )
        for face in faces
    }
    assert styles == {
        (weight, style) for weight in (400, 600, 700) for style in ("normal", "italic")
    }
    for url in fonts:
        resource = ReportResourceFetcher()(url)
        try:
            assert resource.read().startswith(b"wOF2")
        finally:
            resource.close()
    document = HTML(string=html, url_fetcher=ReportResourceFetcher()).render()
    assert document.write_pdf().startswith(b"%PDF-")
    assert {font.family for font in document.fonts.values()} == {"Source Sans 3"}
    assert {font.weight for font in document.fonts.values()} == {400, 600, 700}
    assert any(font.style for font in document.fonts.values())
    assert any(font.weight == 700 and font.style for font in document.fonts.values())


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
        "<style>@font-face {src: url(https://example.invalid/font.woff2)}</style>",
        "<style>@font-face {src: url(file:///private/font.woff2)}</style>",
        "<style>@font-face {src: url(data:font/woff2;base64,bm90IGEgZm9udA==)}</style>",
        "<style>@font-face {src: url(data:font/woff2;base64,invalid!)}</style>",
        "<style>@font-face {src: url(data:image/svg+xml;base64,d09GMg==)}</style>",
        "<foreignObject><div>content</div></foreignObject>",
    ],
)
def test_svg_logo_rejects_active_content_and_external_resources(body):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'.encode()
    with pytest.raises(ValueError):
        validate_report_svg(svg)
    with pytest.raises(ValueError):
        ReportResourceFetcher()("data:image/svg+xml;base64," + b64encode(svg).decode())


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le", "utf-16-be"])
def test_svg_rejects_document_types_independent_of_encoding(encoding):
    """Encoding must not bypass the prohibition on DTD and entity declarations."""
    svg = (
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<!DOCTYPE svg [<!ENTITY text "synthetic">]>'
        '<svg xmlns="http://www.w3.org/2000/svg"><text>&text;</text></svg>'
    ).encode(encoding)
    with pytest.raises(ValueError):
        validate_report_svg(svg)


def test_svg_accepts_self_contained_utf16_without_document_type():
    """Safe encoded logos remain supported after parser-level DTD validation."""
    svg = (
        '<?xml version="1.0" encoding="utf-16"?>'
        '<svg xmlns="http://www.w3.org/2000/svg"><text>synthetic</text></svg>'
    ).encode("utf-16")
    validate_report_svg(svg)
