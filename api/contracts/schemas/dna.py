"""DNA-centric document contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict

from pydantic import AliasChoices, Field, field_validator, model_validator

from api.contracts.schemas.base import _DocBase, _StrictDocBase


class DnaFiltersDoc(_StrictDocBase):
    max_freq: float = Field(default=1.00, ge=0.0, le=1.0)
    min_freq: float = Field(default=0.0, ge=0.0, le=1.0)
    max_control_freq: float = Field(default=0.05, ge=0.0, le=0.5)
    max_popfreq: float = Field(default=0.05, ge=0.0, le=0.5)

    min_depth: int = Field(default=100, ge=0)
    min_alt_reads: int = Field(default=5, ge=0)
    min_cnv_size: int = Field(default=100, ge=0)
    max_cnv_size: int = Field(default=50_000_000, ge=0)

    cnv_loss_cutoff: float = Field(default=-0.3)
    cnv_gain_cutoff: float = Field(default=0.3)

    warn_cov: int = Field(default=100, ge=0)
    error_cov: int = Field(default=10, ge=0)

    genelists: list[str] = Field(
        validation_alias=AliasChoices("genelists", "small_variants_genelists"),
        default_factory=list,
    )
    vep_consequences: list[str] = Field(default_factory=list)
    cnveffects: list[str] = Field(default_factory=lambda: ["gain", "loss"])
    cnv_genelists: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "DnaFiltersDoc":
        """Validate cross-field consistency."""
        if self.min_freq > self.max_freq:
            raise ValueError("min_freq must be less than or equal to max_freq")

        if self.min_depth < self.min_alt_reads:
            raise ValueError("min_depth must be greater than or equal to min_alt_reads")

        if self.min_cnv_size > self.max_cnv_size:
            raise ValueError("min_cnv_size must be less than or equal to max_cnv_size")

        if self.error_cov > self.warn_cov:
            raise ValueError("error_cov must be less than or equal to warn_cov")

        if self.cnv_loss_cutoff >= self.cnv_gain_cutoff:
            raise ValueError("cnv_loss_cutoff must be less than cnv_gain_cutoff")

        allowed_effects = {"gain", "loss"}
        invalid_effects = [effect for effect in self.cnveffects if effect not in allowed_effects]
        if invalid_effects:
            raise ValueError(
                f"cnveffects contains invalid values: {invalid_effects}. "
                f"Allowed values are: {sorted(allowed_effects)}"
            )

        return self


class VariantCsqDoc(_DocBase):
    Feature: str | None = None
    HGNC_ID: str | None = None
    SYMBOL: str | None = None
    PolyPhen: str | None = None
    SIFT: str | None = None
    Consequence: list[str] = Field(default_factory=list)
    ENSP: str | None = None
    BIOTYPE: str | None = None
    INTRON: str | None = None
    EXON: str | None = None
    CANONICAL: str | None = None
    MANE: str | None = None
    STRAND: str | None = None
    IMPACT: str | None = None
    CADD_PHRED: str | None = None
    CLIN_SIG: str | None = None
    VARIANT_CLASS: str | None = None
    HGVSc: str | None = None
    HGVSp: str | None = None


class VariantInfoDoc(_DocBase):
    """
    Variant-centric Info document contracts. Use model_dump(exclude_none=True) to exclude null values.
    """

    variant_callers: list[str] = Field(default_factory=list)
    PON_NUM_tnscope: str | None = None
    PON_VAFS_tnscope: str | None = None
    PON_NUM_vardict: str | None = None
    PON_VAFS_vardict: str | None = None
    PON_NUM_freebayes: str | None = None
    PON_VAFS_freebayes: str | None = None
    PON_FFPE_NUM_freebayes: str | None = None
    PON_FFPE_VAFS_freebayes: str | None = None
    Annotation: str | None = None
    PON_FFPE_NUM_vardict: str | None = None
    PON_FFPE_VAFS_vardict: str | None = None
    CLNSIG: str | None = None
    CLNREVSTAT: str | None = None
    CLNACC: str | None = None
    SCOUT_CUSTOM: str | None = None
    CSQ: list[VariantCsqDoc] = Field(default_factory=list)
    selected_CSQ: VariantCsqDoc
    selected_CSQ_criteria: str

    @field_validator("variant_callers", mode="before")
    @classmethod
    def _normalize_variant_callers(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item for item in value.split("|") if item]
        return value

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "VariantInfoDoc":
        # keys you ALWAYS want to keep even if None
        exclude_keys = {
            "selected_CSQ",
            "selected_CSQ_criteria",
            "CSQ",
            "variant_callers",
        }

        for field_name in list(self.__dict__.keys()):
            if field_name in exclude_keys:
                continue

            if getattr(self, field_name) is None:
                delattr(self, field_name)

        return self


class VariantGtDoc(_DocBase):
    AF: float
    DP: int
    GT: str
    VD: int
    sample: str
    type: str


class VariantsDoc(_DocBase):
    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    ID: str
    QUAL: float
    FILTER: list[str] = Field(default_factory=list)
    INFO: VariantInfoDoc
    GT: list[VariantGtDoc] = Field(default_factory=list)
    gnomad_frequency: float | None = None
    gnomad_max: float | None = None
    exac_frequency: float | None = None
    thousandG_frequency: float | None = None
    variant_class: str | None = None
    selected_csq_feature: str | None = None
    genes: list[str] = Field(default_factory=list)
    transcripts: list[str] = Field(default_factory=list)
    HGVSc: list[str] = Field(default_factory=list)
    HGVSp: list[str] = Field(default_factory=list)
    simple_id: str
    simple_id_hash: str
    cosmic_ids: list[str] = Field(default_factory=list)
    dbsnp_id: str | None = None
    pubmed_ids: list[str] = Field(default_factory=list)
    hotspots: list[dict[str, list[str]]] = Field(default_factory=list)

    @field_validator(
        "gnomad_frequency",
        "gnomad_max",
        "exac_frequency",
        "thousandG_frequency",
        mode="before",
    )
    @classmethod
    def _normalize_optional_frequency(cls, value: Any) -> Any:
        if value in ("", " ", "NA", "N/A", None):
            return None
        return value

    @model_validator(mode="after")
    def _validate_simple_id_and_hash(self) -> "VariantsDoc":
        if not self.simple_id:
            raise ValueError("simple_id is required. Usually it is CHROM_POS_REF_ALT")

        expected_hash = hashlib.md5(self.simple_id.encode("utf-8")).hexdigest()

        if self.simple_id_hash is None:
            self.simple_id_hash = expected_hash
        elif self.simple_id_hash != expected_hash:
            raise ValueError("simple_id_hash does not match simple_id (MD5 mismatch)")

        return self


class CnvGeneDoc(_DocBase):
    gene: str
    class_: str | None = Field(
        validation_alias=AliasChoices("class_", "class"),
        serialization_alias="class",
        default=None,
    )
    cnv_type: str | None = None

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "CnvGeneDoc":
        # keys you ALWAYS want to keep even if None
        exclude_keys = {"gene"}

        for field_name in list(self.__dict__.keys()):
            if field_name in exclude_keys:
                continue

            if getattr(self, field_name) is None:
                delattr(self, field_name)

        return self


class CnvsDoc(_DocBase):
    SAMPLE_ID: str
    chr: str
    start: int
    end: int
    size: int
    ratio: float | None = None
    type: str | None = None
    nprobes: int
    genes: list[CnvGeneDoc] = Field(default_factory=list)
    callers: list[str] = Field(default_factory=list)


class TranslocationInfoAnnDoc(_DocBase):
    Allele: str  # G
    Annotation: list[str] = Field(default_factory=list)  # ["feature_fusion" ]
    Annotation_Impact: str | None = None  # LOW
    Gene_Name: str  # TCF3&ZNF384
    Gene_ID: str  # ENSG00000071564&ENSG00000126746
    Feature_Type: str  # CUSTOM&sorted
    Feature_ID: str  # TCF3_ENSG00000071564&ZNF384_ENSG00000126746
    Transcript_BioType: str | None = None
    Rank: str | None = None
    HGVSc: str | None = (
        None  # t(19%3B12)(p13.3%3Bp13.31)(n.1617928);t(12%3B19)(p13.31%3Bp13.3)(n.6692044)
    )
    HGVSp: str | None = None
    cDNApos: int | None = None
    cDNAlength: int | None = None
    CDSpos: int | None = None
    CDSlength: int | None = None
    AApos: int | None = None
    AAlength: int | None = None
    Distance: str | None = None
    ERRORS: str | None = None
    WARNINGS: str | None = None
    INFO: str | None = None


class TranslocationInfoDoc(_DocBase):
    SVTYPE: str | None = None  # BND
    MATEID: str | None = None  # MantaBND:155054:0:1:0:0:0:1
    SVINSLEN: int | None = None
    SVINSSEQ: str | None = None  # CCCAGATTAGTTAACCCCT
    EVENT: str | None = None  # MantaBND:155054:0:1:0:0:0:0
    SOMATIC: bool  # true
    SOMATICSCORE: int | None = None  # 287
    JUNCTION_SOMATICSCORE: int | None = None  # 145
    BND_DEPTH: int | None = None  # 48
    MATE_BND_DEPTH: int | None = None  # 46
    PANEL: list[str] = Field(default_factory=list)  # fusion|somatic|one
    ANN: list[TranslocationInfoAnnDoc] = Field(default_factory=list)


class TranslocationGtDoc(_DocBase):
    UR: float
    sample: str
    PR: str
    SR: str


class TranslocationsDoc(_DocBase):
    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    FILTER: list[str] = Field(default_factory=list)
    FORMAT: list[str] = Field(default_factory=list)
    ID: str
    QUAL: float
    GT: list[TranslocationGtDoc]
    INFO: list[TranslocationInfoDoc]


class BiomarkersMsiDoc(_DocBase):
    tot: int
    som: int
    per: float


class BiomarkersHrdDoc(_DocBase):
    tai: int
    hrd: int
    lst: int
    sum: int

    @model_validator(mode="after")
    def _validate_sum(self) -> "BiomarkersHrdDoc":
        if self.tai and self.hrd and self.lst:
            sum_expected = self.tai + self.hrd + self.lst
            if self.sum != sum_expected:
                raise ValueError("Sum is not matching with tai, hrd and lst")

        return self


class BiomarkersDoc(_DocBase):
    SAMPLE_ID: str
    name: str
    MSIS: BiomarkersMsiDoc | None = None
    MSIP: BiomarkersMsiDoc | None = None
    HRD: BiomarkersHrdDoc | None = None

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "BiomarkersDoc":
        # keys you ALWAYS want to keep even if None
        exclude_keys = {
            "SAMPLE_ID",
            "name",
        }

        for field_name in list(self.__dict__.keys()):
            if field_name in exclude_keys:
                continue

            if getattr(self, field_name) is None:
                delattr(self, field_name)

        return self


class ReportedVariantsDoc(_DocBase):
    report_id: str
    sample_name: str

    report_oid: Any
    sample_oid: Any
    var_oid: Any
    annotation_oid: Any
    annotation_text_oid: Any
    sample_comment_oid: Any

    simple_id: str
    simple_id_hash: str

    gene: str
    transcript: str
    hgvsc: str
    hgvsp: str
    variant: str

    var_type: str
    tier: int

    created_by: str
    created_on: datetime

    @field_validator("*", mode="before")
    @classmethod
    def no_nulls_allowed(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return v

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v):
        if v not in {1, 2, 3, 4}:
            raise ValueError("tier must be between 1–4")
        return v

    @field_validator("var_type")
    @classmethod
    def validate_var_type(cls, v):
        allowed = {"SNV", "INDEL", "CNV", "FUSION"}
        if v not in allowed:
            raise ValueError(f"var_type must be one of {allowed}")
        return v


class CoverageRegionDoc(_DocBase):
    chr: str
    start: int
    end: int
    nbr: int | None = None
    cov: float | None = None


class ProbeRegionDoc(_DocBase):
    chr: str
    start: int
    end: int
    cov: float | None = None


class TranscriptDoc(_DocBase):
    chr: str
    start: int
    end: int
    transcript_id: str


class GeneCoverageDoc(_DocBase):
    covered_by_panel: bool
    transcript: TranscriptDoc
    exons: Dict[str, CoverageRegionDoc] = Field(default_factory=dict)
    CDS: Dict[str, CoverageRegionDoc] = Field(default_factory=dict)
    probes: Dict[str, ProbeRegionDoc] = Field(default_factory=dict)


class PanelCovDoc(_DocBase):
    genes: Dict[str, GeneCoverageDoc] = Field(default_factory=dict)
    SAMPLE_ID: str
    sample: str


class GroupCoverageDoc(_DocBase):
    genes: Dict[str, GeneCoverageDoc] = Field(default_factory=dict)
    SAMPLE_ID: str
    sample: str
