"""Home payload models used by Flask home blueprint routes."""

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiHomeSamplesPayload(ApiModel):
    live_samples: list[JsonDict] = Field(default_factory=list)
    done_samples: list[JsonDict] = Field(default_factory=list)
    status: str = "live"
    search_mode: str = "live"
    panel_type: str | None = None
    panel_tech: str | None = None
    assay_group: str | None = None


class ApiHomeIsglsPayload(ApiModel):
    items: list[JsonDict] = Field(default_factory=list)


class ApiHomeEffectiveGenesPayload(ApiModel):
    items: list[str] = Field(default_factory=list)
    asp_covered_genes_count: int = 0


class ApiHomeEditContextPayload(ApiModel):
    sample: JsonDict = Field(default_factory=dict)
    asp: JsonDict = Field(default_factory=dict)
    variant_stats_raw: JsonDict = Field(default_factory=dict)
    variant_stats_filtered: JsonDict = Field(default_factory=dict)


class ApiHomeReportContextPayload(ApiModel):
    sample_id: str
    report_id: str
    report_name: str | None = None
    filepath: str | None = None
