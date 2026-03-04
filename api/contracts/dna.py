"""DNA route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DnaVariantsListPayload(BaseModel):
    sample: dict[str, Any]
    meta: dict[str, Any]
    filters: dict[str, Any]
    assay_group: str
    subpanel: str | None = None
    analysis_sections: list[Any]
    assay_config: dict[str, Any]
    assay_config_schema: dict[str, Any] | None = None
    assay_panel_doc: dict[str, Any] | None = None
    assay_panels: list[dict[str, Any]]
    all_panel_genelist_names: list[Any]
    checked_genelists: list[Any]
    checked_genelists_dict: dict[str, Any]
    filter_genes: list[str]
    sample_ids: list[str]
    bam_id: Any
    hidden_comments: bool
    vep_var_class_translations: dict[str, Any]
    vep_conseq_translations: dict[str, Any]
    oncokb_genes: list[str]
    verification_sample_used: str | None = None
    variants: list[dict[str, Any]]
    display_sections_data: dict[str, Any]
    ai_text: str


class DnaPlotContextPayload(BaseModel):
    sample: dict[str, Any]
    assay_config: dict[str, Any]
    assay_config_schema: dict[str, Any] | None = None
    plots_base_dir: str | None = None


class DnaBiomarkersPayload(BaseModel):
    sample: dict[str, Any]
    meta: dict[str, Any]
    biomarkers: list[dict[str, Any]]


class DnaVariantContextPayload(BaseModel):
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    variant: dict[str, Any]
    annotations: list[dict[str, Any]]
    latest_classification: dict[str, Any] | None = None
    other_classifications: list[dict[str, Any]]
    annotations_interesting: list[dict[str, Any]]
    in_other_samples: list[dict[str, Any]]
    in_other: list[dict[str, Any]]
    has_hidden_comments: bool
    hidden_comments: bool
    expression: Any
    civic: Any
    civic_gene: Any
    oncokb: Any
    oncokb_action: Any
    oncokb_gene: Any
    brca_exchange: Any
    iarc_tp53: Any
    assay_group: str
    subpanel: str | None = None
    pon: Any
    sample_ids: list[str]
    bam_id: Any
    vep_var_class_translations: dict[str, Any]
    vep_conseq_translations: dict[str, Any]
    assay_group_mappings: dict[str, Any]


class DnaCnvListPayload(BaseModel):
    sample: dict[str, Any]
    meta: dict[str, Any]
    filters: dict[str, Any]
    cnvs: list[dict[str, Any]]


class DnaCnvContextPayload(BaseModel):
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    cnv: dict[str, Any]
    annotations: list[dict[str, Any]]
    sample_ids: list[str]
    bam_id: Any
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str


class DnaTranslocationsPayload(BaseModel):
    sample: dict[str, Any]
    meta: dict[str, Any]
    translocations: list[dict[str, Any]]


class DnaTranslocationContextPayload(BaseModel):
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    translocation: dict[str, Any]
    annotations: list[dict[str, Any]]
    sample_ids: list[str]
    bam_id: Any
    vep_conseq_translations: dict[str, Any]
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str
