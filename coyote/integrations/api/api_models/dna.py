"""DNA-focused web API payload models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiDnaVariantsPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    filters: JsonDict = Field(default_factory=dict)
    assay_group: str = ""
    subpanel: str | None = None
    analysis_sections: list[str] = Field(default_factory=list)
    assay_config: JsonDict = Field(default_factory=dict)
    assay_config_schema: JsonDict = Field(default_factory=dict)
    assay_panel_doc: JsonDict = Field(default_factory=dict)
    assay_panels: list[JsonDict] = Field(default_factory=list)
    all_panel_genelist_names: list[str] = Field(default_factory=list)
    checked_genelists: list[str] = Field(default_factory=list)
    checked_genelists_dict: JsonDict = Field(default_factory=dict)
    filter_genes: list[str] = Field(default_factory=list)
    sample_ids: JsonDict = Field(default_factory=dict)
    bam_id: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False
    vep_var_class_translations: JsonDict = Field(default_factory=dict)
    vep_conseq_translations: JsonDict = Field(default_factory=dict)
    oncokb_genes: list[str] = Field(default_factory=list)
    verification_sample_used: str | None = None
    variants: list[JsonDict] = Field(default_factory=list)


class ApiDnaPlotContextPayload(ApiModel):
    sample: JsonDict = Field(default_factory=dict)
    assay_config: JsonDict = Field(default_factory=dict)
    assay_config_schema: JsonDict = Field(default_factory=dict)


class ApiDnaBiomarkersPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    biomarkers: list[JsonDict] = Field(default_factory=list)


class ApiDnaVariantDetailPayload(ApiModel):
    sample: JsonDict
    variant: JsonDict
    in_other: list[JsonDict] = Field(default_factory=list)
    annotations: list[JsonDict] | JsonDict = Field(default_factory=list)
    hidden_comments: bool = False
    latest_classification: JsonDict = Field(default_factory=dict)
    expression: JsonDict | list[JsonDict] = Field(default_factory=dict)
    civic: Any | None = None
    civic_gene: Any | None = None
    oncokb: Any | None = None
    oncokb_action: Any | None = None
    oncokb_gene: Any | None = None
    brca_exchange: Any | None = None
    iarc_tp53: Any | None = None
    assay_group: str = ""
    pon: JsonDict | None = None
    other_classifications: list[JsonDict] = Field(default_factory=list)
    subpanel: str | None = None
    sample_ids: JsonDict | list[str] = Field(default_factory=dict)
    bam_id: JsonDict = Field(default_factory=dict)
    annotations_interesting: list[JsonDict] | JsonDict = Field(default_factory=list)
    vep_var_class_translations: JsonDict = Field(default_factory=dict)
    vep_conseq_translations: JsonDict = Field(default_factory=dict)
    assay_group_mappings: JsonDict = Field(default_factory=dict)


class ApiDnaCnvDetailPayload(ApiModel):
    sample: JsonDict
    cnv: JsonDict
    assay_group: str = ""
    annotations: list[JsonDict] | JsonDict = Field(default_factory=list)
    sample_ids: JsonDict | list[str] = Field(default_factory=dict)
    bam_id: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False


class ApiDnaTranslocationDetailPayload(ApiModel):
    sample: JsonDict
    translocation: JsonDict
    assay_group: str = ""
    annotations: list[JsonDict] | JsonDict = Field(default_factory=list)
    sample_ids: JsonDict | list[str] = Field(default_factory=dict)
    bam_id: JsonDict = Field(default_factory=dict)
    vep_conseq_translations: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False


class ApiDnaCnvsPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    filters: JsonDict = Field(default_factory=dict)
    cnvs: list[JsonDict] = Field(default_factory=list)


class ApiDnaTranslocationsPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    translocations: list[JsonDict] = Field(default_factory=list)


class ApiDnaReportPreviewPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    report: JsonDict = Field(default_factory=dict)


class ApiDnaReportSavePayload(ApiModel):
    sample: JsonDict
    report: JsonDict = Field(default_factory=dict)
    meta: JsonDict = Field(default_factory=dict)
