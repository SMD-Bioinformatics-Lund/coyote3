"""Home route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HomeSamplesPayload(BaseModel):
    live_samples: list[dict[str, Any]]
    done_samples: list[dict[str, Any]]
    status: str
    search_mode: str
    sample_view: str = "all"
    profile_scope: str = "production"
    # Backward-compatible summary fields (map to live table pagination)
    page: int = 1
    per_page: int = 30
    # Independent server-side pagination for each table
    live_page: int = 1
    live_per_page: int = 30
    done_page: int = 1
    done_per_page: int = 30
    has_next_live: bool = False
    has_next_done: bool = False
    panel_type: str | None = None
    panel_tech: str | None = None
    assay_group: str | None = None


class HomeItemsPayload(BaseModel):
    items: list[Any]


class HomeEffectiveGenesPayload(HomeItemsPayload):
    asp_covered_genes_count: int


class HomeEditContextPayload(BaseModel):
    sample: dict[str, Any]
    asp: dict[str, Any]
    variant_stats_raw: Any = None
    variant_stats_filtered: Any = None


class HomeMutationStatusPayload(BaseModel):
    status: str
    sample_id: str
    action: str
    isgl_ids: list[str] | None = None
    label: str | None = None
    gene_count: int | None = None


class HomeReportContextPayload(BaseModel):
    sample_id: str
    report_id: str
    report_name: str | None = None
    filepath: str | None = None
