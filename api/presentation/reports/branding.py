"""Load host-owned report branding without coupling the application SDK to a center."""

from base64 import b64encode
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from api.config.paths import API_CONFIG_DIR, CENTER_CONFIG_DIR
from api.config.report_presentation import load_report_presentation
from coyote3.application.reporting.pdf_resources import validate_report_svg
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_renderer import render_report_html


def _image_url(path: Path, *, bundled: bool = False) -> str:
    """Read a small supported logo and return an embedded image URL.

    Args:
        path: Explicitly selected bundled or center-owned logo.
        bundled: Remove editor metadata and screen-only style blocks from the two
            bundled marks. Their visible geometry and ink colours are inline.

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
        if bundled:
            root = ElementTree.fromstring(content)
            for parent in root.iter():
                for child in list(parent):
                    if child.tag.split("}")[-1] in {"style", "namedview"}:
                        parent.remove(child)
            content = ElementTree.tostring(root, encoding="utf-8")
    return f"data:image/{media_type};base64," + b64encode(content).decode()


def load_report_branding(config: dict[str, Any]) -> dict[str, str]:
    """Resolve Coyote3 and center logos from trusted deployment configuration.

    Args:
        config: Host settings. CONTACT.organization.report_logo selects region-skane
            (the bundled default), a path within the center directory, or empty to omit.
            Optional organization.accreditation_logo selects another center-owned image;
            the report displays it only for an accredited assay.
            Organization name, department and address supply report-header text;
            blank or non-text values are omitted. Phone remains a public contact value.

    Returns:
        Embedded logo URLs and configured center identity and contact values.

    Raises:
        ValueError: A custom path escapes the center directory or its logo is unsafe.
        OSError: A configured logo cannot be read.
    """
    assets = API_CONFIG_DIR / "assets"
    branding = {"coyote_logo": _image_url(assets / "coyote.svg", bundled=True)}
    organization = (config.get("CONTACT") or {}).get("organization") or {}
    for field in ("name", "department", "address", "phone"):
        value = organization.get(field)
        if isinstance(value, str) and value.strip():
            branding[f"center_{field}"] = value.strip()
    public_url = ((config.get("CONTACT") or {}).get("support") or {}).get("web_app_base_url")
    if isinstance(public_url, str) and public_url.strip():
        branding["public_base_url"] = public_url.strip().rstrip("/")
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
        branding["center_logo"] = _image_url(path, bundled=choice == "region-skane")
    accreditation = organization.get("accreditation_logo")
    if isinstance(accreditation, str) and accreditation.strip():
        path = (CENTER_CONFIG_DIR / accreditation.strip()).resolve()
        if not path.is_relative_to(CENTER_CONFIG_DIR.resolve()):
            raise ValueError(
                "The accreditation logo must be inside the center configuration directory"
            )
        branding["accreditation_logo"] = _image_url(path)
    return branding


def render_branded_report_html(*, config: dict[str, Any], **report_inputs: Any) -> str:
    """Resolve host branding for the smd-reports renderer.

    Args:
        config: Trusted center configuration used to resolve report logos.
        **report_inputs: Prepared inputs accepted by the core report renderer.

    Returns:
        Standalone report HTML with embedded host-owned branding.
    """
    context = report_inputs.get("template_context") or {}
    presentation = (
        ReportPresentation.model_validate(context["report_presentation"])
        if "report_presentation" in context
        else load_report_presentation()
    )
    return render_report_html(
        **report_inputs,
        branding=load_report_branding(config),
        presentation=presentation,
    )
