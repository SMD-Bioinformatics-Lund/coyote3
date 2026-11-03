"""Server-side report template rendering."""

from __future__ import annotations

from typing import Any

import bleach
import markdown
from jinja2 import ChoiceLoader, Environment, PackageLoader, select_autoescape

from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_context import prepare_render_context
from coyote3.application.reporting.report_service import (
    REPORT_TEMPLATES,
    modern_template_version,
    select_report_template,
    template_content_hash,
)
from coyote3.domain.common.errors import api_error
from coyote3.domain.common.reporting import TIER_NAME, TIER_SHORT_DESC
from coyote3.domain.dna.cnv_metrics import copy_number_from_log2


def _environment(*, modern: bool = False) -> Environment:
    """Return report filters and the selected layout's component lookup order.

    Args:
        modern: Prefer modern presentation components for the selected versioned body.

    Returns:
        An escaping Jinja environment independent of the current working directory.
    """
    loader = PackageLoader("coyote3", "templates/reporting")
    env = Environment(
        loader=ChoiceLoader([PackageLoader("coyote3", "templates/reporting/modern"), loader])
        if modern
        else loader,
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["perc_no_dec"] = _perc_no_dec
    env.filters["unesc"] = _unesc
    env.filters["format_comment"] = _format_comment
    env.filters["sanitize_report_html"] = _sanitize_report_html
    env.filters["format_tier"] = _format_tier
    env.filters["format_classification"] = _format_classification
    env.filters["copy_number"] = _copy_number
    return env


def _copy_number(value: Any) -> str:
    """Format a finite log2-derived diploid copy estimate, or a missing-value marker.

    Args:
        value: Numeric log2 ratio. Missing, nonnumeric or overflowing values are unknown.

    Returns:
        Two-decimal copy-number estimate, or a dash for unusable input.
    """
    import math

    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "-"
    try:
        estimate = copy_number_from_log2(value)
    except OverflowError:
        return "-"
    return f"{estimate:.2f}" if math.isfinite(estimate) else "-"


def _perc_no_dec(value: Any) -> str:
    """Format allele frequency for clinical report display."""
    if value in (None, "", "N/A"):
        return "N/A" if value == "N/A" else "-"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _unesc(value: Any) -> str:
    """Return a text value without HTML escaping entities twice."""
    return str(value or "")


def _format_tier(value: Any, include_label: bool = True) -> str:
    """Format a tier as a Roman numeral, optionally prefixed with its clinical label.

    Args:
        value: Numeric tier; unsupported numeric values display a dash.
        include_label: Include ``Tier`` for detailed wording; false gives a compact numeral.

    Returns:
        Clinical tier label or compact Roman numeral, with a dash for missing values.
    """
    try:
        tier = int(value)
        if tier not in TIER_NAME:
            return "-"
        return f"Tier {TIER_NAME[tier]}" if include_label else TIER_NAME[tier]
    except (TypeError, ValueError):
        return str(value or "-")


def _format_classification(value: Any, description: Any = None) -> str:
    """Render a known tier and optional description, or one plain missing-value hyphen.

    Args:
        value: Numeric classification tier; missing, zero and unclassified values are unknown.
        description: Optional clinical wording. Empty wording or a hyphen is omitted.

    Returns:
        A tier with a plain hyphen separator, or exactly ``-`` for an unknown tier.
    """
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return "-"
    if isinstance(value, bool) or tier not in TIER_NAME:
        return "-"
    label = f"Tier {TIER_NAME[tier]}"
    wording = str(description or "").strip()
    return f"{label} - {wording}" if wording and wording != "-" else label


def _format_comment(value: Any) -> str:
    """Render a stored comment safely for report output."""
    text = str(value or "")
    html = markdown.markdown(text, extensions=["extra", "sane_lists"])
    return _sanitize_report_html(html)


def _sanitize_report_html(value: Any) -> str:
    """Retain report formatting without executable content or embedded resources.

    Args:
        value: Authored HTML; null produces empty text.

    Returns:
        Allowlisted HTML safe for insertion into a report's body, not attributes.
    """
    return bleach.clean(
        str(value or ""),
        tags=[
            "p",
            "br",
            "strong",
            "em",
            "b",
            "i",
            "ul",
            "ol",
            "li",
            "code",
            "pre",
            "blockquote",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "div",
            "span",
            "u",
            "sub",
            "sup",
            "h2",
            "h3",
            "h4",
            "hr",
        ],
        attributes={
            "a": ["href", "title"],
            "td": ["colspan", "rowspan"],
            "th": ["colspan", "rowspan"],
        },
        protocols={"http", "https", "mailto"},
        strip=True,
    )


def render_report_html(
    *,
    template_name: str,
    template_context: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    analyte: str,
    preview: bool,
    organization_name: str = "",
    generated_by: str = "",
    layout: str | None = None,
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
        layout: Optional presentation override, legacy or modern. None uses the
            approved template profile, falling back to the established legacy layout.
        branding: Host-provided embedded logo URLs for modern presentation. None omits images.
        presentation: Validated modern-report wording. None retains the existing Swedish text.

    Returns:
        Escaped HTML suitable for browser preview and PDF rendering.

    Raises:
        AppError: The installed template differs from the approved configuration layout.
        ValueError: The layout or modern template manifest is invalid.
        OSError: A required packaged template asset is missing or unreadable.
    """
    _ = snapshot_rows
    context = prepare_render_context(template_context, analyte=analyte, preview=preview)
    context.update(organization_name=organization_name, generated_by=generated_by)
    selected_template = "report_fusion.html" if analyte == "rna" else "dna_report.html"
    if template_name in REPORT_TEMPLATES:
        selected_template = template_name
    template_release = (template_context.get("assay_config") or {}).get("template_release")
    if template_release:
        selected_template = template_release.get("template_name", "")
        if selected_template not in REPORT_TEMPLATES or (
            template_release.get("content_hash") != template_content_hash(selected_template)
        ):
            raise api_error(422, "The approved report template revision is not installed")
    try:
        leaf, configured_layout = select_report_template(selected_template, analyte)
    except ValueError as exc:
        raise api_error(422, str(exc)) from exc
    selected_layout = layout or configured_layout
    if selected_layout not in {"legacy", "modern"}:
        raise ValueError("Report layout must be legacy or modern")
    context["report_body_template"] = (
        REPORT_TEMPLATES[
            "modern/dna_report.html" if analyte == "dna" else "modern/report_fusion.html"
        ][1]
        if selected_layout == "modern"
        else leaf
    )
    context.update(report_analyte=analyte, branding=branding or {})
    context["assay_accredited"] = (
        (context["assay_config"].get("assay_resource_release") or {}).get("content") or {}
    ).get("accredited") is True
    if selected_layout == "modern":
        context["report_template_version"] = modern_template_version(analyte)
        context.setdefault("class_desc_short", TIER_SHORT_DESC)
        sections = dict(context.get("report_sections_data") or {})
        for key in ("snvs", "germline_snvs"):
            if key in sections:
                sections[key] = [
                    {
                        **row,
                        "summary_variant": row.get("variant"),
                        "variant": (row.get("protein_changes") or [row.get("variant")])[-1],
                        "protein_changes": (row.get("protein_changes") or [])[-1:],
                    }
                    for row in sections[key]
                ]
        context["report_sections_data"] = sections
    settings = presentation or ReportPresentation.model_validate(
        context.get("report_presentation") or {}
    )
    context["empty_result_messages"] = settings.empty_results.model_dump()
    return (
        _environment(modern=selected_layout == "modern")
        .get_template("modern/report.html" if selected_layout == "modern" else leaf)
        .render(**context)
    )


def render_pdf_bytes(html: str) -> bytes:
    """Render a PDF byte stream from report HTML."""
    from weasyprint import HTML

    from coyote3.application.reporting.pdf_resources import ReportResourceFetcher

    return HTML(string=html, url_fetcher=ReportResourceFetcher()).write_pdf(
        presentational_hints=False
    )
