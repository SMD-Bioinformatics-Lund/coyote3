# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Per-build DNA report state; no persistence or global mutable state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc


@dataclass
class DnaReportState:
    """Keep inputs and intermediate results private to one report build."""

    sample: dict[str, Any]
    assay_config: dict[str, Any]
    save: int
    include_snapshot: bool
    clinical_rule_override: ClinicalRuleSetDoc | None
    clinical_rule_only: bool
    clinical_rule_condition_trace: bool
    sample_assay: str | None = field(init=False)
    assay_group: str = field(init=False)
    diagnosis: str | None = field(init=False)
    report_sections: list[str] = field(init=False)
    report_sections_data: dict[str, Any] = field(init=False)
    assay_panel_doc: dict[str, Any] = field(init=False)
    sample_filters: dict[str, Any] = field(init=False)
    active_snv_intents: list[str] = field(init=False)
    primary_snv_intent: str = field(init=False)
    genes_covered_in_panel: dict[str, Any] = field(init=False)
    filter_genes: list[str] = field(init=False)
    sample_vep_version: str = field(init=False)
    conseq_terms_mapper: dict[str, Any] = field(init=False)
    snv_filters: dict[str, Any] = field(init=False)
    cnv_filters: dict[str, Any] = field(init=False)
    filter_conseq: list[str] = field(init=False)
    disp_pos: list[Any] = field(init=False)
    variants: list[dict[str, Any]] = field(init=False)
    latest_sample_comment: dict[str, Any] | None = field(init=False)
    snapshot_rows: list[dict[str, Any]] = field(init=False)
    rule_sections_data: dict[str, Any] = field(init=False)
    germline_variants: list[dict[str, Any]] = field(init=False)
    clinical_rule_evaluation: Any = field(init=False)
