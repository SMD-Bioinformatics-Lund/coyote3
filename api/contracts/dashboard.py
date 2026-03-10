"""Dashboard route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DashboardSummaryPayload(BaseModel):
    total_samples: int
    analysed_samples: int
    pending_samples: int
    user_samples_stats: dict[str, Any]
    variant_stats: dict[str, Any]
    unique_gene_count_all_panels: int
    assay_gene_stats_grouped: dict[str, Any]
    sample_stats: dict[str, Any]
    tier_stats: dict[str, Any] = {}
    quality_stats: dict[str, Any] = {}
    dashboard_meta: dict[str, Any] = {}
    admin_insights: dict[str, Any] = {}
    capacity_counts: dict[str, Any] = {}
    isgl_visibility: dict[str, Any] = {}
