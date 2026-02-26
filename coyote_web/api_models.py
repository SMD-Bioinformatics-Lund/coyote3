"""Typed response models for web->API integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiRnaFusionsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    filter_context: dict[str, Any] = Field(default_factory=dict)
    fusions: list[dict[str, Any]] = Field(default_factory=list)


class ApiDnaVariantsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    variants: list[dict[str, Any]] = Field(default_factory=list)


class ApiRnaFusionDetailPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    fusion: dict[str, Any]
    annotations: dict[str, Any] = Field(default_factory=dict)
    latest_classification: dict[str, Any] = Field(default_factory=dict)
    other_classifications: list[dict[str, Any]] = Field(default_factory=list)
    annotations_interesting: dict[str, Any] = Field(default_factory=dict)
    in_other: dict[str, Any] = Field(default_factory=dict)
    hidden_comments: bool = False
    assay_group: str = ""
    subpanel: str | None = None
    assay_group_mappings: dict[str, Any] = Field(default_factory=dict)


class ApiDnaVariantDetailPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    variant: dict[str, Any]
    in_other: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
    hidden_comments: bool = False
    latest_classification: dict[str, Any] = Field(default_factory=dict)
    expression: list[dict[str, Any]] = Field(default_factory=list)
    civic: dict[str, Any] | None = None
    civic_gene: dict[str, Any] | None = None
    oncokb: dict[str, Any] | None = None
    oncokb_action: Any | None = None
    oncokb_gene: dict[str, Any] | None = None
    brca_exchange: dict[str, Any] | None = None
    iarc_tp53: dict[str, Any] | None = None
    assay_group: str = ""
    pon: dict[str, Any] | None = None
    other_classifications: list[dict[str, Any]] = Field(default_factory=list)
    subpanel: str | None = None
    sample_ids: list[str] = Field(default_factory=list)
    bam_id: dict[str, Any] = Field(default_factory=dict)
    annotations_interesting: dict[str, Any] = Field(default_factory=dict)
    vep_var_class_translations: dict[str, Any] = Field(default_factory=dict)
    vep_conseq_translations: dict[str, Any] = Field(default_factory=dict)
    assay_group_mappings: dict[str, Any] = Field(default_factory=dict)


class ApiDnaCnvDetailPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    cnv: dict[str, Any]
    assay_group: str = ""
    annotations: dict[str, Any] = Field(default_factory=dict)
    sample_ids: list[str] = Field(default_factory=list)
    bam_id: dict[str, Any] = Field(default_factory=dict)
    hidden_comments: bool = False


class ApiDnaTranslocationDetailPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    translocation: dict[str, Any]
    assay_group: str = ""
    annotations: dict[str, Any] = Field(default_factory=dict)
    bam_id: dict[str, Any] = Field(default_factory=dict)
    vep_conseq_translations: dict[str, Any] = Field(default_factory=dict)
    hidden_comments: bool = False


class ApiDnaCnvsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    cnvs: list[dict[str, Any]] = Field(default_factory=list)


class ApiDnaTranslocationsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    translocations: list[dict[str, Any]] = Field(default_factory=list)
