# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Coverage route API contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CoverageGeneListOption(BaseModel):
    """A selectable gene list captured in the applied configuration."""

    id: str
    label: str


class CoverageIntervalPayload(BaseModel):
    """Stored legacy interval evidence; endpoints and null depth remain unchanged."""

    id: str
    chr: str
    start: int
    end: int
    avg_cov: float | None
    amplicon: str | None = None


class CoverageSamplePayload(BaseModel):
    """D4 gene coverage or legacy interval evidence for an authorized sample."""

    coverage_format: Literal["d4", "interval"] = "d4"
    intervals: list[CoverageIntervalPayload] = Field(default_factory=list)
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
