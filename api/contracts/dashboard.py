"""Dashboard route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardSummaryPayload(BaseModel):
    """Represent the dashboard summary payload."""

    total_samples: int
    analysed_samples: int
    pending_samples: int
    user_samples_stats: dict[str, Any]
    variant_stats: dict[str, Any]
    unique_gene_count_all_panels: int
    assay_gene_stats_grouped: dict[str, Any]
    panel_gene_stats_grouped: dict[str, Any] = Field(default_factory=dict)
    panel_portfolio: dict[str, Any] = Field(default_factory=dict)
    panel_analysis_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    sample_stats: dict[str, Any]
    user_scope_summary: dict[str, Any] = Field(default_factory=dict)
    tier_stats: dict[str, Any] = Field(default_factory=dict)
    top_tiered_genes: list[dict[str, Any]] = Field(default_factory=list)
    reported_tier_stats: dict[str, Any] = Field(default_factory=dict)
    quality_stats: dict[str, Any] = Field(default_factory=dict)
    dashboard_meta: dict[str, Any] = Field(default_factory=dict)
    admin_insights: dict[str, Any] = Field(default_factory=dict)
    capacity_counts: dict[str, Any] = Field(default_factory=dict)
    isgl_visibility: dict[str, Any] = Field(default_factory=dict)
    isgl_association: dict[str, Any] = Field(default_factory=dict)


class DashboardAdminInsightsPayload(BaseModel):
    """Represent flexible administrative dashboard insight payloads."""

    model_config = ConfigDict(extra="allow")


class DashboardRefreshQueuedPayload(BaseModel):
    """Represent an asynchronously queued dashboard metrics refresh."""

    status: str
    task_id: str
