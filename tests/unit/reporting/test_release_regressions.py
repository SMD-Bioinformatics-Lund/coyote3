"""Release gates for unconditional rules and restricted PDF resources."""

import pytest

from api.application.reporting.clinical_rules.terminology_defaults import build_default_terminology
from api.application.reporting.clinical_rules.validation import validate_rule_set
from api.application.reporting.report_renderer import _report_resource_fetcher, render_pdf_bytes
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
        _report_resource_fetcher(url)


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
    assert calls["url_fetcher"] is _report_resource_fetcher
