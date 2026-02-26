"""DNA-focused web API payload models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from coyote_web.api_models.base import ApiModel, JsonDict


class ApiDnaVariantsPayload(ApiModel):
    sample: JsonDict
    meta: JsonDict = Field(default_factory=dict)
    filters: JsonDict = Field(default_factory=dict)
    variants: list[JsonDict] = Field(default_factory=list)


class ApiDnaVariantDetailPayload(ApiModel):
    sample: JsonDict
    variant: JsonDict
    in_other: JsonDict = Field(default_factory=dict)
    annotations: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False
    latest_classification: JsonDict = Field(default_factory=dict)
    expression: list[JsonDict] = Field(default_factory=list)
    civic: JsonDict | None = None
    civic_gene: JsonDict | None = None
    oncokb: JsonDict | None = None
    oncokb_action: Any | None = None
    oncokb_gene: JsonDict | None = None
    brca_exchange: JsonDict | None = None
    iarc_tp53: JsonDict | None = None
    assay_group: str = ""
    pon: JsonDict | None = None
    other_classifications: list[JsonDict] = Field(default_factory=list)
    subpanel: str | None = None
    sample_ids: list[str] = Field(default_factory=list)
    bam_id: JsonDict = Field(default_factory=dict)
    annotations_interesting: JsonDict = Field(default_factory=dict)
    vep_var_class_translations: JsonDict = Field(default_factory=dict)
    vep_conseq_translations: JsonDict = Field(default_factory=dict)
    assay_group_mappings: JsonDict = Field(default_factory=dict)


class ApiDnaCnvDetailPayload(ApiModel):
    sample: JsonDict
    cnv: JsonDict
    assay_group: str = ""
    annotations: JsonDict = Field(default_factory=dict)
    sample_ids: list[str] = Field(default_factory=list)
    bam_id: JsonDict = Field(default_factory=dict)
    hidden_comments: bool = False


class ApiDnaTranslocationDetailPayload(ApiModel):
    sample: JsonDict
    translocation: JsonDict
    assay_group: str = ""
    annotations: JsonDict = Field(default_factory=dict)
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
