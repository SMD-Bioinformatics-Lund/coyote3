"""Application-owned governance configuration contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionCatalog:
    """Fixed permission categories supplied by the COYOTE3 application."""

    categories: tuple[str, ...]


PERMISSION_CATALOG = PermissionCatalog(
    categories=(
        "Analysis Actions",
        "Application Control Management",
        "Assay Configuration Management",
        "Assay Panel Management",
        "Audit & Monitoring",
        "Data Downloads",
        "Gene List Management",
        "Permission Policy Management",
        "Reports",
        "Role Management",
        "Sample Management",
        "Schema Management",
        "User Management",
        "Variant Curation",
        "Visualization",
    )
)
