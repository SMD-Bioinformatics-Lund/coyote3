"""Application-owned assay-group identifiers.

These identifiers are persisted clinical workflow scope. They connect ASPs,
ASPCs, ISGLs, annotations, user access, and group-specific query behaviour,
so they must not be center-configurable.
"""

from __future__ import annotations

ASP_GROUP_OPTIONS: tuple[str, ...] = (
    "hematology",
    "solid",
    "pgx",
    "tumwgs",
    "wts",
    "myeloid",
    "lymphoid",
    "fusion",
)
