"""RNA route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RnaFusionListPayload(BaseModel):
    """Represent the rna fusion list payload."""

    sample: dict[str, Any]
    meta: dict[str, Any]
    assay_group: str
    subpanel: str | None = None
    analysis_sections: list[Any]
    assay_config: dict[str, Any]
    assay_config_schema: dict[str, Any] | None = None
    assay_panel_doc: dict[str, Any] | None = None
    sample_ids: dict[str, str]
    hidden_comments: bool
    fusionlist_options: list[dict[str, Any]]
    checked_fusionlists: list[Any]
    checked_fusionlists_dict: dict[str, Any]
    filters: dict[str, Any]
    filter_context: dict[str, Any]
    fusions: list[dict[str, Any]]
    ai_text: str
    fusion_caller_options: list[str] = Field(default_factory=list)
    fusion_annotation_metadata: dict[str, list[str]] = Field(default_factory=dict)


class RnaFusionContextPayload(BaseModel):
    """Represent the rna fusion context payload."""

    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    fusion: dict[str, Any]
    in_other: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    latest_classification: dict[str, Any] | None = None
    annotations_interesting: dict[str, Any]
    other_classifications: list[dict[str, Any]]
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str
    subpanel: str | None = None
    assay_group_mappings: dict[str, Any]
    fusion_caller_options: list[str] = Field(default_factory=list)
    fusion_annotation_metadata: dict[str, list[str]] = Field(default_factory=dict)
    cosmic: dict[str, Any]


class RnaAnalysisPayload(BaseModel):
    """Represent expression, classification, and quality records for an RNA sample."""

    sample_id: str
    sample_name: str
    expression: dict[str, Any] = Field(default_factory=dict)
    classification: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)


class RnaFusionExportRow(BaseModel):
    """Represent one fusion CSV export row."""

    gene_1: str = ""
    gene_2: str = ""
    effect: str = ""
    spanning_pairs: str = ""
    unique_spanning_reads: str = ""
    breakpoint_1: str = ""
    breakpoint_2: str = ""
    tier: str = ""
    callers: str = ""
    description: str = ""
    status: str = ""
    false_positive: str = ""
    irrelevant: str = ""
    blacklisted: str = ""
    interesting: str = ""
    latest_comment: str = ""
    latest_comment_author: str = ""
    latest_comment_time: str = ""


class RnaCsvExportContextPayload(BaseModel):
    """Represent CSV download context for RNA routes."""

    filename: str
    content: str
    row_count: int
