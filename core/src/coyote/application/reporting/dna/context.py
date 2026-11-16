# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Per-build DNA report state; no persistence or global mutable state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc


class DnaReportState(BaseModel):
    """Keep inputs and intermediate results private to one report build."""

    sample: dict[str, Any]
    assay_config: dict[str, Any]
    save: int
    include_snapshot: bool
    clinical_rule_override: ClinicalRuleSetDoc | None
    clinical_rule_only: bool
    clinical_rule_condition_trace: bool
    sample_assay: str | None = None
    assay_group: str = ""
    diagnosis: str | None = None
    report_sections: list[str] = Field(default_factory=list)
    report_sections_data: dict[str, Any] = Field(default_factory=dict)
    assay_panel_doc: dict[str, Any] = Field(default_factory=dict)
    sample_filters: dict[str, Any] = Field(default_factory=dict)
    active_snv_intents: list[str] = Field(default_factory=list)
    primary_snv_intent: str = ""
    genes_covered_in_panel: dict[str, Any] = Field(default_factory=dict)
    filter_genes: list[str] = Field(default_factory=list)
    sample_vep_version: str = ""
    conseq_terms_mapper: dict[str, Any] = Field(default_factory=dict)
    snv_filters: dict[str, Any] = Field(default_factory=dict)
    cnv_filters: dict[str, Any] = Field(default_factory=dict)
    filter_conseq: list[str] = Field(default_factory=list)
    disp_pos: list[Any] = Field(default_factory=list)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    latest_sample_comment: dict[str, Any] | None = None
    snapshot_rows: list[dict[str, Any]] = Field(default_factory=list)
    rule_sections_data: dict[str, Any] = Field(default_factory=dict)
    germline_variants: list[dict[str, Any]] = Field(default_factory=list)
    clinical_rule_evaluation: Any = None
