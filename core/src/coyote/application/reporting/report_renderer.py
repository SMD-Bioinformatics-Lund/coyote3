# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Server-side report template rendering."""

from __future__ import annotations

import json
from typing import Any

from smd_reports import ReportLoader, ReportRenderer
from weasyprint import HTML

from coyote.application.reporting.document import ReportDocumentBuilder
from coyote.application.reporting.pdf_resources import ReportResourceFetcher
from coyote.application.reporting.presentation import ReportPresentation
from coyote.application.reporting.report_context import prepare_render_context
from coyote.application.reporting.report_service import (
    select_report_template,
    template_content_hash,
)
from coyote.domain.common.errors import api_error


def render_report_html(
    *,
    template_name: str,
    template_context: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    analyte: str,
    preview: bool,
    organization_name: str = "",
    generated_by: str = "",
    branding: dict[str, str] | None = None,
    presentation: ReportPresentation | None = None,
) -> str:
    """Render report HTML with explicitly supplied institutional and user identity.

    Args:
        template_name: DNA or RNA report template identifier.
        template_context: Validated workflow data and clinical text.
        snapshot_rows: Finding snapshots retained by the caller, not rendered directly.
        analyte: DNA or RNA workflow used to select the default template.
        preview: Whether to display the preview marker.
        organization_name: Configured performing institution; empty omits the row.
        generated_by: Authenticated user's display name or username; empty shows Unknown.
        branding: Host-provided embedded logo URLs. None omits images.
        presentation: Validated report wording. None retains the existing Swedish text.

    Returns:
        Escaped HTML suitable for browser preview and PDF rendering.

    Raises:
        AppError: The installed template differs from the approved configuration layout.
        ValueError: The layout, SMD document or embedded artwork is invalid.
        OSError: A required packaged template asset is missing or unreadable.
    """
    _ = snapshot_rows
    context = prepare_render_context(template_context, analyte=analyte, preview=preview)
    context.update(organization_name=organization_name, generated_by=generated_by)
    selected_template = template_name
    template_release = (template_context.get("assay_config") or {}).get("template_release")
    if template_release:
        selected_template = template_release.get("template_name", "")
    try:
        select_report_template(selected_template, analyte)
    except ValueError as exc:
        raise api_error(422, str(exc)) from exc
    if template_release and template_release.get("content_hash") != template_content_hash(
        selected_template
    ):
        raise api_error(422, "The approved report template revision is not installed")
    context.update(report_analyte=analyte, branding=branding or {})
    context["assay_accredited"] = (
        (context["assay_config"].get("assay_resource_release") or {}).get("content") or {}
    ).get("accredited") is True
    settings = presentation or ReportPresentation.model_validate(
        context.get("report_presentation") or {}
    )
    document = ReportLoader().loads(
        json.dumps(
            ReportDocumentBuilder(
                context,
                analyte=analyte,
                preview=preview,
                presentation=settings,
            ).build(),
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    html = ReportRenderer().render_html(document)
    # Keep the application's browser policy around the package-owned document.
    policy = (
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
        "font-src data:; base-uri 'none'; form-action 'none'\">"
    )
    return html.replace("<head>", "<head>" + policy, 1)


def render_pdf_bytes(html: str) -> bytes:
    """Render a PDF byte stream from report HTML."""
    return HTML(string=html, url_fetcher=ReportResourceFetcher()).write_pdf(
        presentational_hints=False
    )
