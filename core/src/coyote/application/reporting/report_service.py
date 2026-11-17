# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Select smd-reports documents and verify their published template identities."""

from enum import StrEnum
from hashlib import sha256
from importlib.metadata import version
from importlib.resources import files

REPORT_PRESET = "coyote3"


class ReportTemplate(StrEnum):
    """Supported clinical report identities, independent of renderer file names."""

    DNA = "dna"
    RNA = "rna"


def template_content_hash(template_name: str) -> str:
    """Fingerprint smd-reports and the input adapter for a registered template identity.

    Args:
        template_name: DNA or RNA report identifier from an approved profile or workflow.

    Returns:
        SHA-256 covering the installed package resources and input projection.

    Raises:
        ValueError: The report identifier is unsupported.
        OSError: An installed renderer resource cannot be read.
    """
    template = ReportTemplate(template_name)
    digest = sha256(
        f"smd-reports:{version('smd-reports')}:{REPORT_PRESET}:{template.value}".encode()
    )

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
    include(files("coyote").joinpath("application/reporting/document"), "document/")
    for name in ("ordering.py", "report_context.py", "report_renderer.py", "report_service.py"):
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
    try:
        template = ReportTemplate(template_name)
    except ValueError as exc:
        raise ValueError("The report template does not support this assay modality") from exc
    if template.value != analyte:
        raise ValueError("The report template does not support this assay modality")
    return template.value
