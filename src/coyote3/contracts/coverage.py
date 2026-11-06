"""Coverage route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CoverageGeneListOption(BaseModel):
    """A selectable gene list captured in the applied configuration."""

    id: str
    label: str


class CoverageSamplePayload(BaseModel):
    """Represent the coverage sample payload."""

    coverage: dict[str, Any]
    cov_cutoff: int
    sample: dict[str, Any]
    gene_scope: list[str]
    gene_list_id: str | None = None
    gene_lists: list[CoverageGeneListOption] = Field(default_factory=list)
    smp_grp: str
    cov_table: dict[str, dict[str | int, Any]]


class CoverageBlacklistedPayload(BaseModel):
    """Represent the coverage blacklisted payload."""

    blacklisted: dict[str, dict[str, Any]]
    group: str
