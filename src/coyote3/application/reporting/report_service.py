"""Select packaged report layouts and verify their published template identities."""

import re
from hashlib import sha256
from importlib.resources import files

REPORT_TEMPLATES = {
    "dna_report.html": ("dna", "legacy/dna.html", "legacy"),
    "report_fusion.html": ("rna", "legacy/rna.html", "legacy"),
    "modern/dna_report.html": ("dna", "legacy/dna.html", "modern"),
    "modern/report_fusion.html": ("rna", "legacy/rna.html", "modern"),
}
_INCLUDE = re.compile(r"{% include ['\"]([^'\"]+)['\"] %}")


def _expanded_source(name: str) -> str:
    """Expand literal component includes for a template-content digest.

    Args:
        name: Package-relative registered template, component or stylesheet path.

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

    Notes:
        Empty extension blocks and include boundaries produce no legacy content.
        Expanding them preserves the pre-extraction digest; edits to legacy HTML
        or CSS still change it. Modern digests additionally cover modern overrides.
    """
    _, leaf, layout = REPORT_TEMPLATES[template_name]
    base = _expanded_source("base.html")
    for block in ("format_head", "format_notice"):
        base = base.replace("{% block " + block + " %}{% endblock %}", "")
    body = _expanded_source(leaf).replace('"legacy/report.html"', '"report_layout.html"')
    # The preselected-call view is prepared in Python. Its canonical legacy spelling
    # retains approved digests for the same selected flags and displayed values.
    body = body.replace(
        "var.report_selected_calls", "var.calls|selectattr('selected', 'equalto', 1)|list"
    )
    content = base + body
    if layout == "modern":
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
