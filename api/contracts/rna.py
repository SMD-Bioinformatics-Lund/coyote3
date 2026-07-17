"""RNA route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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
    interesting: str = ""
    latest_comment: str = ""
    latest_comment_author: str = ""
    latest_comment_time: str = ""


class RnaCsvExportContextPayload(BaseModel):
    """Represent CSV download context for RNA routes."""

    filename: str
    content: str
    row_count: int
