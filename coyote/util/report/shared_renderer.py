"""Render report JSON and compose the separate Flask preview page."""

import json
from typing import Any

from flask import render_template, url_for
from smd_reports import ReportLoader, ReportRenderer


def render_report(document: dict[str, Any]) -> str:
    """Render the public shared-template JSON contract as standalone HTML.

    Args:
        document: Metadata and conditional report sections prepared by Coyote3.

    Returns:
        Complete report HTML without application controls or scripts.

    Raises:
        ValueError: Report input or an embedded image is invalid.
        smd_reports.ReportRenderError: The installed template cannot be rendered.
    """
    return ReportRenderer().render_html(ReportLoader().loads(json.dumps(document)))


def render_preview(html: str, sample: dict, analyte: str, panel_export: dict | None = None) -> str:
    """Compose the application preview around an isolated report frame.

    Args:
        html: Standalone HTML returned by smd-reports.
        sample: Sample metadata for the heading and navigation.
        analyte: dna or rna, selecting the existing sample and save routes.
        panel_export: Encrypted DNA panel/filter export fields, or None.

    Returns:
        Preview page with a separate finalize action using the protected save route.
    """
    return render_template(
        "report_preview.html",
        report_html=html,
        sample=sample,
        analyte=analyte,
        finalize_url=url_for(f"{analyte}_bp.save_{analyte}_report", sample_id=sample["name"]),
        sample_url=url_for(
            f"{analyte}_bp.{'list_variants' if analyte == 'dna' else 'list_fusions'}",
            sample_id=sample["name"],
        ),
        panel_export=panel_export,
    )
