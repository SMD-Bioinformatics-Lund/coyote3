"""DNA route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DnaVariantsListPayload(BaseModel):
    """Represent the dna variants list payload.
    """
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
    sample_ids: dict[str, str]
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
    """Represent the dna plot context payload.
    """
    sample: dict[str, Any]
    assay_config: dict[str, Any]
    assay_config_schema: dict[str, Any] | None = None
    plots_base_dir: str | None = None


class DnaBiomarkersPayload(BaseModel):
    """Represent the dna biomarkers payload.
    """
    sample: dict[str, Any]
    meta: dict[str, Any]
    biomarkers: list[dict[str, Any]]


class DnaVariantContextPayload(BaseModel):
    """Represent the dna variant context payload.
    """
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    variant: dict[str, Any]
    annotations: list[dict[str, Any]]
    latest_classification: dict[str, Any] | None = None
    other_classifications: list[dict[str, Any]]
    annotations_interesting: dict[str, Any]
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
    sample_ids: dict[str, str]
    bam_id: Any
    vep_var_class_translations: dict[str, Any]
    vep_conseq_translations: dict[str, Any]
    assay_group_mappings: dict[str, Any]


class DnaCnvListPayload(BaseModel):
    """Represent the dna cnv list payload.
    """
    sample: dict[str, Any]
    meta: dict[str, Any]
    filters: dict[str, Any]
    cnvs: list[dict[str, Any]]


class DnaCnvContextPayload(BaseModel):
    """Represent the dna cnv context payload.
    """
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    cnv: dict[str, Any]
    annotations: list[dict[str, Any]]
    sample_ids: dict[str, str]
    bam_id: Any
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str


class DnaTranslocationsPayload(BaseModel):
    """Represent the dna translocations payload.
    """
    sample: dict[str, Any]
    meta: dict[str, Any]
    translocations: list[dict[str, Any]]


class DnaTranslocationContextPayload(BaseModel):
    """Represent the dna translocation context payload.
    """
    sample: dict[str, Any]
    sample_summary: dict[str, Any]
    translocation: dict[str, Any]
    annotations: list[dict[str, Any]]
    sample_ids: dict[str, str]
    bam_id: Any
    vep_conseq_translations: dict[str, Any]
    has_hidden_comments: bool
    hidden_comments: bool
    assay_group: str


class DnaSnvExportRow(BaseModel):
    """Represent one SNV CSV export row."""

    gene: str = ""
    hgvsp: str = ""
    hgvsc: str = ""
    exon: str = ""
    intron: str = ""
    var_type: str = ""
    indel_size: str = ""
    consequence: str = ""
    pop_freq: str = ""
    tier: str = ""
    chr_pos: str = ""
    flags: str = ""
    case_gt: str = ""
    control_gt: str = ""
    false_positive: str = ""
    irrelevant: str = ""
    interesting: str = ""
    blacklisted: str = ""
    latest_comment: str = ""
    latest_comment_author: str = ""
    latest_comment_time: str = ""


class DnaCnvExportRow(BaseModel):
    """Represent one CNV CSV export row."""

    genes: str = ""
    region: str = ""
    size_bp: str = ""
    callers: str = ""
    copy_number: str = ""
    purity_copy_number: str = ""
    ref_alt_reads: str = ""
    status: str = ""
    artefact: str = ""
    false_positive: str = ""
    irrelevant: str = ""
    interesting: str = ""
    latest_comment: str = ""
    latest_comment_author: str = ""
    latest_comment_time: str = ""


class DnaTranslocExportRow(BaseModel):
    """Represent one translocation CSV export row."""

    gene_1: str = ""
    gene_2: str = ""
    positions: str = ""
    var_type: str = ""
    hgvsp: str = ""
    hgvsc: str = ""
    panel: str = ""
    status: str = ""
    false_positive: str = ""
    interesting: str = ""
    latest_comment: str = ""
    latest_comment_author: str = ""
    latest_comment_time: str = ""


class DnaCsvExportContextPayload(BaseModel):
    """Represent CSV download context for web proxy routes."""

    filename: str
    content: str
    row_count: int
