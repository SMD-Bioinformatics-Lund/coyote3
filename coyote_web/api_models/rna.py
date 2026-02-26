"""RNA-focused web API payload models."""

from __future__ import annotations

from pydantic import Field

from coyote_web.api_models.base import ApiModel, JsonDict


class ApiRnaFusionsPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    filters: JsonDict = Field(default_factory=dict)
    filter_context: JsonDict = Field(default_factory=dict)
    fusions: list[JsonDict] = Field(default_factory=list)


class ApiRnaFusionDetailPayload(ApiModel):
    sample: JsonDict
    fusion: JsonDict
    annotations: JsonDict = Field(default_factory=dict)
    latest_classification: JsonDict = Field(default_factory=dict)
    other_classifications: list[JsonDict] = Field(default_factory=list)
    annotations_interesting: JsonDict = Field(default_factory=dict)
    in_other: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False
    assay_group: str = ""
    subpanel: str | None = None
    assay_group_mappings: JsonDict = Field(default_factory=dict)


class ApiRnaReportPreviewPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    report: JsonDict = Field(default_factory=dict)
