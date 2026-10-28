"""The alternate report preserves established clinical content and renders in memory."""

from html.parser import HTMLParser

import pytest

from api.presentation.reports.modern import render_modern_report_html
from coyote3.application.reporting.report_renderer import render_pdf_bytes, render_report_html


class BodyText(HTMLParser):
    """Collect clinical text while excluding styles, branding and the trial-only notice."""

    def __init__(self):
        """Prepare an empty body-text collector."""
        super().__init__()
        self.body = False
        self.notice = False
        self.brand = False
        self.label = False
        self.print_depth = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        """Track body entry and the additional temporary-preview notice."""
        if tag == "body":
            self.body = True
        if tag == "div" and (
            self.print_depth
            or dict(attrs).get("class")
            in {
                "report-page-header",
                "report-page-footer",
                "report-page-number-footer",
            }
        ):
            self.print_depth += 1
        if tag == "header" and dict(attrs).get("class") in {
            "report-brand-header",
            "report-document-heading",
        }:
            self.brand = True
        if tag == "h2" and dict(attrs).get("class") == "report-metadata-heading":
            self.label = True
        if tag == "p" and dict(attrs).get("class") == "trial-notice":
            self.notice = True

    def handle_endtag(self, tag):
        """Stop collecting outside the body and resume after the trial notice."""
        if tag == "body":
            self.body = False
        if tag == "div" and self.print_depth:
            self.print_depth -= 1
        if tag == "p":
            self.notice = False
        if tag == "header":
            self.brand = False
        if tag == "h2":
            self.label = False

    def handle_data(self, data):
        """Retain nonblank body text without changing its clinical wording."""
        if (
            self.body
            and not self.notice
            and not self.brand
            and not self.label
            and not self.print_depth
            and data.strip()
        ):
            self.text.append(data.strip())


@pytest.mark.parametrize(
    "analyte,template", [("dna", "dna_report.html"), ("rna", "report_fusion.html")]
)
def test_alternate_layout_preserves_all_report_text_and_embeds_its_css(analyte, template):
    context = {
        "sample": {"name": "SYNTHETIC_TRIAL", "case": {}, "control": {}},
        "assay_config": {"reporting": {"report_header": "Synthetic report"}},
        "report_header": "Synthetic report",
        "report_sections": ["SNV"] if analyte == "dna" else [],
        "report_sections_data": {
            "snvs": [
                {
                    "symbol": "SYNTHETIC_GENE",
                    "indel_size": 0,
                    "variant": "p.Val1Ala",
                    "cdna": "c.2T>C",
                    "af": 0.42,
                    "class_short_desc": "Synthetic classification",
                    "class_long_desc": "Synthetic interpretation",
                    "class": 1,
                    "global_annotations": [],
                    "annotations_interesting": {},
                    "protein_changes": ["p.Val1Ala"],
                }
            ]
        },
        "fusions": [
            {
                "gene1": "SYNTHETIC_A",
                "gene2": "SYNTHETIC_B",
                "classification": {"class": 1},
                "calls": [
                    {
                        "selected": 1,
                        "spanpairs": 12,
                        "spanreads": 25,
                        "effect": "in-frame",
                        "breakpoint1": "1:100",
                        "breakpoint2": "2:200",
                    }
                ],
                "global_annotations": [],
            }
        ]
        if analyte == "rna"
        else [],
        "class_desc_short": {1: "Synthetic classification"},
        "class_desc": {1: "Synthetic interpretation"},
        "genes_covered_in_panel": {},
    }
    established = render_report_html(
        template_name=template,
        template_context=context,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
    )
    alternate = render_modern_report_html(
        template_name=template,
        template_context=context,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
    )
    original_text, alternate_text = BodyText(), BodyText()
    original_text.feed(established)
    alternate_text.feed(alternate)
    assert alternate_text.text == original_text.text
    if analyte == "dna":
        assert "SYNTHETIC_GENE" in alternate_text.text
        assert "Synthetic classification" in alternate_text.text
    else:
        assert "SYNTHETIC_A - SYNTHETIC_B" in alternate_text.text
        assert "Synthetic classification" in alternate_text.text
    assert '<style id="modern-report-style">' in alternate
    assert "Content-Security-Policy" in alternate
    assert '<link rel="stylesheet"' not in alternate
    assert "PREVIEW · UNSAVED REPORT" in alternate
    pdf = render_pdf_bytes(alternate)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
