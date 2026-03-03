"""RNA route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RnaFusionListPayload(BaseModel):
    sample: dict[str, Any]
    meta: dict[str, Any]
    assay_group: str
    subpanel: str | None = None
    analysis_sections: list[Any]
    assay_config: dict[str, Any]
    assay_config_schema: dict[str, Any] | None = None
    assay_panel_doc: dict[str, Any] | None = None
    sample_ids: list[str]
    hidden_comments: bool
    fusionlist_options: list[dict[str, Any]]
    checked_fusionlists: list[Any]
    checked_fusionlists_dict: dict[str, Any]
    filters: dict[str, Any]
    filter_context: dict[str, Any]
    fusions: list[dict[str, Any]]
    ai_text: str


class RnaFusionContextPayload(BaseModel):
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    fusion: dict[str, Any]
    in_other: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    latest_classification: dict[str, Any] | None = None
    annotations_interesting: list[dict[str, Any]]
    other_classifications: list[dict[str, Any]]
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str
    subpanel: str | None = None
    assay_group_mappings: dict[str, Any]
