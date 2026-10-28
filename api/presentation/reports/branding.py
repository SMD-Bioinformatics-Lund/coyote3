"""Load host-owned report branding without coupling the application SDK to a center."""

from base64 import b64encode
from pathlib import Path
from typing import Any

from api.config.paths import API_CONFIG_DIR, CENTER_CONFIG_DIR
from api.config.report_presentation import load_report_presentation
from coyote3.application.reporting.pdf_resources import validate_report_svg
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_renderer import render_report_html


def _image_url(path: Path) -> str:
    """Read a small supported logo and return an embedded image URL.

    Args:
        path: Explicitly selected bundled or center-owned logo.

    Returns:
        Data URL requiring no network or filesystem access while rendering.

    Raises:
        ValueError: The logo is oversized, unsupported, or contains unsafe SVG content.
        OSError: The selected logo cannot be read.
    """
    media_type = {".svg": "svg+xml", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}.get(
        path.suffix.lower()
    )
    if not media_type or path.stat().st_size > 1024 * 1024:
        raise ValueError("Report logos must be SVG, PNG or JPEG files under one megabyte")
    content = path.read_bytes()
    if media_type == "svg+xml":
        validate_report_svg(content)
    return f"data:image/{media_type};base64," + b64encode(content).decode()


def load_report_branding(config: dict[str, Any]) -> dict[str, str]:
    """Resolve Coyote3 and center logos from trusted deployment configuration.

    Args:
        config: Host settings. CONTACT.organization.report_logo selects region-skane
            (the bundled default), a path within the center directory, or empty to omit.
            Optional organization.address and organization.phone supply the public
            center contact details; blank or non-text values are omitted.

    Returns:
        Embedded logo URLs and optional center address and telephone for the report header.

    Raises:
        ValueError: A custom path escapes the center directory or its logo is unsafe.
        OSError: A configured logo cannot be read.
    """
    assets = API_CONFIG_DIR / "assets"
    branding = {"coyote_logo": _image_url(assets / "coyote.svg")}
    organization = (config.get("CONTACT") or {}).get("organization") or {}
    for field in ("address", "phone"):
        value = organization.get(field)
        if isinstance(value, str) and value.strip():
            branding[f"center_{field}"] = value.strip()
    choice = str(
        ((config.get("CONTACT") or {}).get("organization") or {}).get("report_logo", "region-skane")
    )
    if choice:
        path = assets / "region-skane.svg"
        if choice != "region-skane":
            path = (CENTER_CONFIG_DIR / choice).resolve()
            if not path.is_relative_to(CENTER_CONFIG_DIR.resolve()):
                raise ValueError(
                    "The report logo must be inside the center configuration directory"
                )
        branding["center_logo"] = _image_url(path)
    return branding


def render_branded_report_html(*, config: dict[str, Any], **report_inputs: Any) -> str:
    """Resolve host branding only when rendering a modern report.

    Args:
        config: Trusted center configuration used to resolve report logos.
        **report_inputs: Prepared inputs accepted by the core report renderer.

    Returns:
        Standalone report HTML with embedded host-owned branding.
    """
    context = report_inputs.get("template_context") or {}
    release = (context.get("assay_config") or {}).get("template_release") or {}
    template = release.get("template_name", report_inputs.get("template_name", ""))
    layout = report_inputs.get("layout")
    modern = layout == "modern" or (layout is None and template.startswith("modern/"))
    presentation = None
    if modern:
        presentation = (
            ReportPresentation.model_validate(context["report_presentation"])
            if "report_presentation" in context
            else load_report_presentation()
        )
    return render_report_html(
        **report_inputs,
        branding=load_report_branding(config) if modern else None,
        presentation=presentation,
    )
