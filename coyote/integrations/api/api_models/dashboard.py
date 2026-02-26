"""Dashboard-focused web API payload models."""

from __future__ import annotations

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiDashboardSummaryPayload(ApiModel):
    total_samples: int = 0
    analysed_samples: int = 0
    pending_samples: int = 0
    user_samples_stats: list[JsonDict] = Field(default_factory=list)
    variant_stats: JsonDict = Field(default_factory=dict)
    unique_gene_count_all_panels: int = 0
    assay_gene_stats_grouped: JsonDict = Field(default_factory=dict)
    sample_stats: JsonDict = Field(default_factory=dict)

