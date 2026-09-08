"""Release gates for unconditional rules and restricted PDF resources."""

import base64
from io import BytesIO

import pytest
from PIL import Image

from api.application.reporting.clinical_rules.terminology_defaults import build_default_terminology
from api.application.reporting.clinical_rules.validation import validate_rule_set
from api.application.reporting.pdf_resources import ReportResourceFetcher
from api.application.reporting.report_renderer import render_pdf_bytes
from tests.unit.reporting.test_clinical_rules import _document


def test_unconditional_rule_validates_and_default_terminology_is_independent():
    document = _document()
    document.blocks[0].rules[0].condition = None
    assert validate_rule_set(document).valid
    first = build_default_terminology()
    first.clear()
    assert build_default_terminology()


@pytest.mark.parametrize(
    "url", ["https://example.test/image.png", "file:///etc/passwd", "data:image/svg+xml,<svg/>"]
)
def test_report_resources_cannot_read_network_or_files(url):
    with pytest.raises(ValueError, match="embedded PNG or JPEG"):
        ReportResourceFetcher()(url)


def test_presentational_hints_remain_disabled(monkeypatch):
    calls = {}

    class Renderer:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def write_pdf(self, **kwargs):
            calls.update(kwargs)
            return b"pdf"

    monkeypatch.setattr("weasyprint.HTML", Renderer)
    assert render_pdf_bytes("<body background='untrusted'>") == b"pdf"
    assert calls["presentational_hints"] is False
    assert isinstance(calls["url_fetcher"], ReportResourceFetcher)


def test_oversized_report_resource_is_rejected():
    with pytest.raises(ValueError, match="size limit"):
        ReportResourceFetcher()("data:image/png;base64," + "A" * (20 * 1024 * 1024))


@pytest.mark.parametrize("format_name,mime", [("PNG", "png"), ("JPEG", "jpeg")])
def test_embedded_report_images_and_actual_pdf(format_name, mime):
    image = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format=format_name)
    data = image.getvalue()
    url = f"data:image/{mime};base64," + base64.b64encode(data).decode("ascii")
    response = ReportResourceFetcher()(url)
    try:
        assert response.read() == data
    finally:
        response.close()
    pdf = render_pdf_bytes(f'<p>Synthetic report</p><img src="{url}">')
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Image" in pdf
