"""Select packaged report layouts and verify their published template identities."""

import re
import tomllib
from hashlib import sha256
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, Field

REPORT_TEMPLATES = {
    "dna_report.html": ("dna", "legacy/dna.html", "legacy"),
    "report_fusion.html": ("rna", "legacy/rna.html", "legacy"),
    "modern/dna_report.html": ("dna", "legacy/dna.html", "modern"),
    "modern/report_fusion.html": ("rna", "legacy/rna.html", "modern"),
}
_INCLUDE = re.compile(r"{% include ['\"]([^'\"]+)['\"] %}")


class _TemplateRelease(BaseModel):
    """Version metadata for one modern report analyte."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class _TemplateManifest(BaseModel):
    """Independent DNA and RNA releases packaged with the modern presentation bundle."""

    model_config = ConfigDict(extra="forbid", strict=True)

    dna: _TemplateRelease
    rna: _TemplateRelease


def modern_template_version(analyte: str) -> str:
    """Read the selected modern report's version from its packaged manifest.

    Args:
        analyte: Report modality, either dna or rna.

    Returns:
        The selected analyte's template release in MAJOR.MINOR.PATCH format.

    Raises:
        OSError: The packaged manifest is missing or unreadable.
        ValueError: The analyte is unsupported.
        tomllib.TOMLDecodeError: The manifest is not valid TOML.
        pydantic.ValidationError: The version is missing, malformed, or has unknown fields.

    Notes:
        There is no default version when metadata is invalid. The version participates
        in the approved template content hash, independently of patient report numbering.
    """
    if analyte not in {"dna", "rna"}:
        raise ValueError("Template version requires a DNA or RNA analyte")
    manifest = _TemplateManifest.model_validate(
        tomllib.loads(_expanded_source("modern/manifest.toml"))
    )
    return manifest.dna.version if analyte == "dna" else manifest.rna.version


def _expanded_source(name: str) -> str:
    """Expand literal component includes for a template-content digest.

    Args:
        name: Package-relative template, component, stylesheet or manifest path.

    Returns:
        Source with includes expanded using Jinja's final-newline semantics.
    """
    source = files("coyote3").joinpath("templates/reporting", name).read_text(encoding="utf-8")
    return _INCLUDE.sub(lambda match: _expanded_source(match[1]).removesuffix("\n"), source)


def template_content_hash(template_name: str) -> str:
    """Hash report content while retaining existing approved legacy digests.

    Args:
        template_name: Registered legacy or modern DNA/RNA template identifier.

    Returns:
        SHA-256 covering the selected report's layout, components and embedded CSS.

    Raises:
        KeyError: The template identifier is not registered.
        ValueError: The modern template manifest is malformed or has invalid metadata.
        OSError: A packaged template asset is missing or unreadable.

    Notes:
        Empty extension blocks and include boundaries produce no legacy content.
        Expanding them preserves the pre-extraction digest; edits to legacy HTML
        or CSS still change it. Modern digests additionally cover modern overrides.
    """
    analyte, leaf, layout = REPORT_TEMPLATES[template_name]
    base = _expanded_source("base.html")
    for block in ("format_head", "format_notice"):
        base = base.replace("{% block " + block + " %}{% endblock %}", "")
    body = _expanded_source(leaf).replace('"legacy/report.html"', '"report_layout.html"')
    # Presentation-only blocks leave legacy output byte-for-byte unchanged.
    for block in (
        "snv_table",
        "germline_snv_table",
        "cnv_table",
        "translocation_table",
        "biomarker_table",
        "pgx_table",
        "fusion_table",
        "fusion_details",
    ):
        body = body.replace("{% block " + block + " scoped %}", "")
        body = body.replace("{% endblock " + block + " %}", "")
    # The preselected-call view is prepared in Python. Its canonical legacy spelling
    # retains approved digests for the same selected flags and displayed values.
    body = body.replace(
        "var.report_selected_calls", "var.calls|selectattr('selected', 'equalto', 1)|list"
    )
    content = base + body
    if layout == "modern":
        content += modern_template_version(analyte)
        content += _expanded_source("modern/report.html")
        content += _expanded_source(
            f"modern/components/{REPORT_TEMPLATES[template_name][0]}/sample_information.html"
        )
    return sha256(content.encode()).hexdigest()


def select_report_template(template_name: str, analyte: str) -> tuple[str, str]:
    """Resolve a registered layout and reject a template for another analyte.

    Args:
        template_name: Registered template identity from the workflow or approved profile.
        analyte: DNA or RNA clinical workflow supplying the report data.

    Returns:
        Legacy body template and selected layout name.

    Raises:
        ValueError: The identifier is unregistered or incompatible with the analyte.
    """
    if template_name not in REPORT_TEMPLATES or REPORT_TEMPLATES[template_name][0] != analyte:
        raise ValueError("The report template does not support this assay modality")
    _, leaf, layout = REPORT_TEMPLATES[template_name]
    return leaf, layout
