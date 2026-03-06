"""Coverage route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CoverageSamplePayload(BaseModel):
    coverage: dict[str, Any]
    cov_cutoff: int
    sample: dict[str, Any]
    genelists: list[str]
    smp_grp: str
    cov_table: dict[str, dict[str, Any]]


class CoverageBlacklistedPayload(BaseModel):
    blacklisted: dict[str, dict[str, Any]]
    group: str
