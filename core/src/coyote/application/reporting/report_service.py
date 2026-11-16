# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Select smd-reports documents and verify their published template identities."""

from hashlib import sha256
from importlib.resources import files

REPORT_TEMPLATES = {
    "smd/dna_report.html": "dna",
    "smd/report_fusion.html": "rna",
}


def template_content_hash(template_name: str) -> str:
    """Fingerprint smd-reports and the input adapter for a registered template identity.

    Args:
        template_name: Registered DNA or RNA identifier; only canonical smd-reports identities are accepted.

    Returns:
        SHA-256 covering the installed package resources and input projection.

    Raises:
        KeyError: The template identifier is not registered.
        OSError: An installed renderer resource cannot be read.
    """
    return smd_template_content_hash(REPORT_TEMPLATES[template_name])


def smd_template_content_hash(analyte: str) -> str:
    """Fingerprint the installed rendering package and the Coyote4 input projection.

    Args:
        analyte: DNA or RNA report modality.

    Returns:
        SHA-256 of package identity, renderer assets and the application adapter.

    Raises:
        ValueError: The modality is unsupported.
        OSError: An installed rendering resource cannot be read.
    """
    from smd_reports import __version__

    if analyte not in {"dna", "rna"}:
        raise ValueError("Template identity requires a DNA or RNA analyte")
    digest = sha256(f"smd-reports:{__version__}:{analyte}".encode())

    def include(directory, prefix=""):
        """Hash renderer resources in stable path order, excluding interpreter caches."""
        for resource in sorted(directory.iterdir(), key=lambda item: item.name):
            path = prefix + resource.name
            if resource.is_dir() and resource.name != "__pycache__":
                include(resource, path + "/")
            elif resource.is_file() and resource.name.endswith(
                (".py", ".html", ".css", ".json", ".woff2", ".svg", ".png")
            ):
                digest.update(path.encode())
                digest.update(resource.read_bytes())

    include(files("smd_reports"))
    for name in ("smd_input.py", "ordering.py", "report_context.py", "report_renderer.py"):
        digest.update(files("coyote").joinpath("application/reporting", name).read_bytes())
    return digest.hexdigest()


def select_report_template(template_name: str, analyte: str) -> str:
    """Validate the canonical renderer identity and its report modality.

    Args:
        template_name: Registered template identity from the workflow or approved profile.
        analyte: DNA or RNA clinical workflow supplying the report data.

    Returns:
        The canonical template identity unchanged.

    Raises:
        ValueError: The identifier is unregistered or incompatible with the analyte.
    """
    if template_name not in REPORT_TEMPLATES or REPORT_TEMPLATES[template_name] != analyte:
        raise ValueError("The report template does not support this assay modality")
    return template_name
