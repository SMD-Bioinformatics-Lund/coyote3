"""DNA-centric document contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import AliasChoices, Field, field_validator, model_validator

from api.contracts.schemas.base import (
    _DocBase,
    _FindingDocBase,
    _StrictCollectionDocBase,
    _StrictDocBase,
)
from api.contracts.schemas.normalizers import normalize_ampersand_terms


class DnaFiltersDoc(_StrictDocBase):
    """Flat DNA filter thresholds and gene-list selections with cross-field checks."""

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

    snvlists: list[str] = Field(default_factory=list)
    vep_consequences: list[str] = Field(default_factory=list)
    cnveffects: list[str] = Field(default_factory=lambda: ["gain", "loss"])
    cnvlists: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _apply_field_defaults_for_unset_values(cls, data: Any) -> Any:
        """Treat null and empty list filter values as unset so defaults apply."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        scalar_defaults_to_restore = {
            "max_freq",
            "min_freq",
            "max_control_freq",
            "max_popfreq",
            "min_depth",
            "min_alt_reads",
            "min_cnv_size",
            "max_cnv_size",
            "cnv_loss_cutoff",
            "cnv_gain_cutoff",
            "warn_cov",
            "error_cov",
        }
        list_defaults_to_restore = {
            "snvlists",
            "vep_consequences",
            "cnveffects",
            "cnvlists",
        }

        for key in scalar_defaults_to_restore:
            if key in normalized and normalized[key] is None:
                normalized.pop(key, None)
        for key in list_defaults_to_restore:
            if key in normalized and (
                normalized[key] is None
                or (isinstance(normalized[key], list) and len(normalized[key]) == 0)
            ):
                normalized.pop(key, None)
        return normalized

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
    """Transcript consequence annotations with normalized consequence and significance lists."""

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
    STRAND: str | None = None
    IMPACT: str | None = None
    CADD_PHRED: str | None = None
    CLIN_SIG: list[str] = Field(default_factory=list)
    VARIANT_CLASS: str | None = None
    HGVSc: str | None = None
    HGVSp: str | None = None

    @field_validator("Consequence", "CLIN_SIG", mode="before")
    @classmethod
    def _normalize_term_lists(cls, value: Any) -> list[str]:
        """Split ampersand-delimited annotation terms and remove blanks and duplicates.

        Args:
            value: Scalar or iterable of terms; null and empty input give no terms.

        Returns:
            Stripped terms in first-occurrence order.
        """
        return normalize_ampersand_terms(value)


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
    PON_FFPE_NUM_vardict: str | None = None
    PON_FFPE_VAFS_vardict: str | None = None
    CLNSIG: str | None = None
    CLNREVSTAT: str | None = None
    CLNACC: str | None = None
    SCOUT_CUSTOM: str | None = None
    selected_CSQ: VariantCsqDoc
    selected_CSQ_criteria: str

    @field_validator("variant_callers", mode="before")
    @classmethod
    def _normalize_variant_callers(cls, value: Any) -> Any:
        """Split pipe-delimited caller names without changing their case or whitespace.

        Args:
            value: Caller string or existing collection; null and empty strings give no callers.

        Returns:
            Nonempty pipe-separated tokens for strings, an empty list for unset input,
            or other input unchanged for subsequent validation.
        """
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item for item in value.split("|") if item]
        return value

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "VariantInfoDoc":
        """Remove null-valued attributes except the required identity or payload fields.

        Returns:
            This model after deleting null attributes other than selected_CSQ, selected_CSQ_criteria, and variant_callers.

        Notes:
            Attributes are deleted in place, including null extra fields.
        """
        # keys you ALWAYS want to keep even if None
        exclude_keys = {
            "selected_CSQ",
            "selected_CSQ_criteria",
            "variant_callers",
        }

        for field_name in list(self.__dict__.keys()):
            if field_name in exclude_keys:
                continue

            if getattr(self, field_name) is None:
                delattr(self, field_name)

        return self


class VariantGtDoc(_DocBase):
    """Per-sample genotype with allele frequency, total depth, and alternate-read count."""

    AF: float
    DP: int
    GT: str
    VD: int
    sample: str
    type: str


class VariantsDoc(_FindingDocBase):
    """Sample-scoped small variant with selected consequence and hashed genomic identity."""

    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    ID: str
    QUAL: Optional[float] = None
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
    consequence_terms: list[str] = Field(default_factory=list)
    simple_id: str
    simple_id_hash: str
    cosmic_ids: list[str] = Field(default_factory=list)
    dbsnp_id: str | None = None
    pubmed_ids: list[str] = Field(default_factory=list)
    hotspots: list[dict[str, list[str]]] = Field(default_factory=list)
    fp: str | bool = ""
    irrelevant: str | bool = ""
    interesting: str | bool = ""

    @field_validator("consequence_terms", mode="before")
    @classmethod
    def _normalize_consequence_terms(cls, value: Any) -> list[str]:
        """Expand ampersand-delimited consequences without stripping term whitespace.

        Args:
            value: Scalar or list, tuple, or set of terms; null and empty strings give no terms.

        Returns:
            Nonempty terms in encounter order with duplicates removed.
        """
        if value in (None, ""):
            return []
        raw_values = value.split("&") if isinstance(value, str) else value
        if not isinstance(raw_values, (list, tuple, set)):
            raw_values = [raw_values]
        return list(
            dict.fromkeys(
                term for item in raw_values for term in str(item or "").split("&") if term
            )
        )

    @field_validator(
        "gnomad_frequency",
        "gnomad_max",
        "exac_frequency",
        "thousandG_frequency",
        mode="before",
    )
    @classmethod
    def _normalize_optional_frequency(cls, value: Any) -> Any:
        """Translate supported missing-frequency markers to null.

        Args:
            value: Frequency or missing marker: empty string, one space, NA, N/A, or None.

        Returns:
            None for a missing marker; otherwise the input for numeric validation.
        """
        if value in ("", " ", "NA", "N/A", None):
            return None
        return value

    @model_validator(mode="after")
    def _validate_simple_id_and_hash(self) -> "VariantsDoc":
        """Check the genomic identifier and its UTF-8 MD5 digest.

        Returns:
            This variant, filling the hash if it is None when this validator runs.

        Raises:
            ValueError: If simple_id is empty or its supplied hash differs from the digest.

        Notes:
            Field validation precedes this check; this does not make the required
            simple_id_hash field nullable in the public contract.
        """
        if not self.simple_id:
            raise ValueError("simple_id is required. Usually it is CHROM_POS_REF_ALT")

        expected_hash = hashlib.md5(self.simple_id.encode("utf-8")).hexdigest()

        if self.simple_id_hash is None:
            self.simple_id_hash = expected_hash
        elif self.simple_id_hash != expected_hash:
            raise ValueError("simple_id_hash does not match simple_id (MD5 mismatch)")

        return self


class CnvGeneDoc(_DocBase):
    """Gene affected by a CNV with optional classification and copy-number type."""

    gene: str
    class_: str | None = Field(
        validation_alias=AliasChoices("class_", "class"),
        serialization_alias="class",
        default=None,
    )
    cnv_type: str | None = None

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "CnvGeneDoc":
        """Remove null-valued attributes except the required identity or payload fields.

        Returns:
            This model after deleting null attributes other than gene.

        Notes:
            Attributes are deleted in place, including null extra fields.
        """
        # keys you ALWAYS want to keep even if None
        exclude_keys = {"gene"}

        for field_name in list(self.__dict__.keys()):
            if field_name in exclude_keys:
                continue

            if getattr(self, field_name) is None:
                delattr(self, field_name)

        return self


class CnvsDoc(_FindingDocBase):
    """Sample-scoped copy-number interval with ratio, genes, probes, and callers."""

    SAMPLE_ID: str
    chr: str
    start: int
    end: int
    size: int
    ratio: float | None = None
    type: str | None = None
    nprobes: int = 0
    genes: list[CnvGeneDoc] = Field(default_factory=list)
    callers: list[str] = Field(default_factory=list)

    @field_validator("ratio", mode="before")
    @classmethod
    def _normalize_ratio(cls, value: Any) -> Any:
        """Convert numeric or symbolic copy-number ratios to floats.

        Args:
            value: Number, numeric text, or DEL/LOSS/AMP/DUP/GAIN label.

        Returns:
            A float, with DEL/LOSS mapped to -1, AMP to 1, and DUP/GAIN to 0.5.
            Null, empty, and unparseable values produce None.
        """
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        raw = str(value).strip().upper()
        symbolic = {
            "DEL": -1.0,
            "LOSS": -1.0,
            "AMP": 1.0,
            "DUP": 0.5,
            "GAIN": 0.5,
        }
        if raw in symbolic:
            return symbolic[raw]
        try:
            return float(raw)
        except ValueError:
            return None

    @field_validator("callers", mode="before")
    @classmethod
    def _normalize_callers(cls, value: Any) -> Any:
        """Parse and lowercase copy-number caller names.

        Args:
            value: Comma-, pipe-, or semicolon-delimited text, a collection, or a scalar.

        Returns:
            Stripped nonblank caller strings, retaining duplicates; null or empty
            input produces an empty list.
        """
        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw = value.replace("|", ",").replace(";", ",")
            return [token.strip().lower() for token in raw.split(",") if token.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        text = str(value).strip().lower()
        return [text] if text else []


class TranslocationInfoAnnDoc(_DocBase):
    """Structural-variant consequence annotation with gene and transcript coordinates."""

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
    """Structural-variant INFO fields with all and selected MANE annotations."""

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
    MANE_ANN: TranslocationInfoAnnDoc | None = None


class TranslocationGtDoc(_DocBase):
    """Sample-level translocation support fields from the genotype payload."""

    UR: float | None = None
    sample: str
    PR: str
    SR: str


class TranslocationsDoc(_FindingDocBase):
    """Sample-scoped structural variant with breakend, genotype, and annotation fields."""

    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    FILTER: list[str] = Field(default_factory=list)
    FORMAT: list[str] = Field(default_factory=list)
    ID: str
    QUAL: Optional[float] = None
    GT: list[TranslocationGtDoc]
    INFO: TranslocationInfoDoc
    fp: str | bool = ""
    irrelevant: str | bool = ""
    interesting: str | bool = ""
    blacklisted: str | bool = ""


class BiomarkersMsiDoc(_DocBase):
    """MSI total and somatic counts with the reported percentage."""

    tot: int
    som: int
    per: float


class BiomarkersHrdDoc(_DocBase):
    """HRD component scores and a conditionally checked combined score."""

    tai: int
    hrd: int
    lst: int
    sum: int

    @model_validator(mode="after")
    def _validate_sum(self) -> "BiomarkersHrdDoc":
        """Check the combined score only when all three component scores are nonzero.

        Returns:
            This HRD result unchanged.

        Raises:
            ValueError: If all components are truthy and sum differs from tai + hrd + lst.
        """
        if self.tai and self.hrd and self.lst:
            sum_expected = self.tai + self.hrd + self.lst
            if self.sum != sum_expected:
                raise ValueError("Sum is not matching with tai, hrd and lst")

        return self


class BiomarkersDoc(_DocBase):
    """Sample biomarker results with absent optional assays removed after validation."""

    SAMPLE_ID: str
    name: str
    MSIS: BiomarkersMsiDoc | None = None
    MSIP: BiomarkersMsiDoc | None = None
    HRD: BiomarkersHrdDoc | None = None

    @model_validator(mode="after")
    def _cleanup_none_fields(self) -> "BiomarkersDoc":
        """Remove null-valued attributes except the required identity or payload fields.

        Returns:
            This model after deleting null attributes other than SAMPLE_ID and name.

        Notes:
            Attributes are deleted in place, including null extra fields.
        """
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


class PgxDoc(_DocBase):
    """Sample-scoped PGX payload preserved from the declared ingest result."""

    SAMPLE_ID: str


class ReportedVariantsDoc(_StrictCollectionDocBase):
    """Immutable, explicitly typed finding included in a saved report."""

    report_id: str
    report_num: int | None = None
    sample_name: str

    report_oid: Any
    sample_oid: Any
    assay: str | None = None
    assay_group: str | None = None
    subpanel: str | None = None
    environment: str | None = None
    analysis_type: str
    analysis_intent: str | None = None
    finding_type: str | None = None
    var_oid: Any | None = None
    annotation_oid: Any | None = None
    annotation_text_oid: Any | None = None
    sample_comment_oid: Any | None = None

    simple_id: str
    simple_id_hash: str

    genes: list[str] = Field(default_factory=list)
    gene: str | None = None
    gene1: str | None = None
    gene2: str | None = None
    transcript: str | None = None
    hgvsc: str | None = None
    hgvsp: str | None = None
    genomic: str | None = None
    nomenclature: str | None = None
    variant: str | None = None

    var_type: str | None = None
    tier: int | None = None

    # Copy-number snapshot fields.
    region: str | None = None
    chromosome: str | None = None
    start: int | None = None
    end: int | None = None
    size: int | None = None
    cnv_type: str | None = None
    ratio: float | None = None
    nprobes: int | None = None

    # Structural-variant and fusion snapshot fields.
    source_id: str | None = None
    position: int | None = None
    ref: str | None = None
    alt: str | None = None
    breakpoint: str | None = None
    breakpoint_1: str | None = None
    breakpoint_2: str | None = None
    fusion: str | None = None
    effect: Any | None = None
    spanning_pairs: int | None = None
    spanning_reads: int | None = None
    longest_anchor: int | None = None
    callers: list[str] = Field(default_factory=list)
    classification: int | None = None
    text: str | None = None

    # Biomarker and pharmacogenomic snapshot fields.
    biomarker: str | None = None
    result: Any | None = None
    pgx_result: Any | None = None
    diplotype: str | None = None
    phenotype: str | None = None
    activity_score: Any | None = None
    recommendation: Any | None = None

    created_by: str
    created_on: datetime

    @model_validator(mode="before")
    @classmethod
    def reject_generic_finding_payload(cls, value: Any) -> Any:
        """Reject the generic finding_data field in a reported finding.

        Args:
            value: Raw report-finding input before model validation.

        Returns:
            The input unchanged when no prohibited field is present.

        Raises:
            ValueError: If a dictionary contains finding_data, even when its value is null.
        """
        if isinstance(value, dict) and "finding_data" in value:
            raise ValueError(
                "finding_data is not part of the reported finding contract; "
                "store report-time values in their named fields"
            )
        return value

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v):
        """Restrict a supplied report tier to the four supported levels.

        Args:
            v: Tier after field parsing, or None when no tier was captured.

        Returns:
            The tier unchanged, including None.

        Raises:
            ValueError: If the tier is not 1, 2, 3, or 4.
        """
        if v is None:
            return v
        if v not in {1, 2, 3, 4}:
            raise ValueError("tier must be between 1–4")
        return v

    @field_validator("var_type")
    @classmethod
    def validate_var_type(cls, v):
        """Check a report snapshot's optional variant-type label.

        Args:
            v: Uppercase type label, or None when no label was captured.

        Returns:
            The type unchanged, including None.

        Raises:
            ValueError: If the label is not SNV, INDEL, CNV, FUSION, TRANSLOCATION,
                BIOMARKER, or PGX.
        """
        if v is None:
            return v
        allowed = {"SNV", "INDEL", "CNV", "FUSION", "TRANSLOCATION", "BIOMARKER", "PGX"}
        if v not in allowed:
            raise ValueError(f"var_type must be one of {allowed}")
        return v


class CoverageRegionDoc(_DocBase):
    """Genomic coverage interval with optional region number and depth."""

    chr: str
    start: int
    end: int
    nbr: int | None = None
    cov: float | None = None


class ProbeRegionDoc(_DocBase):
    """Probe interval with optional coverage depth."""

    chr: str
    start: int
    end: int
    cov: float | None = None


class TranscriptDoc(_DocBase):
    """Transcript identifier and genomic interval used for coverage display."""

    chr: str
    start: int
    end: int
    transcript_id: str


class GeneCoverageDoc(_DocBase):
    """Panel membership and transcript, exon, CDS, and probe coverage for one gene."""

    covered_by_panel: bool
    transcript: TranscriptDoc
    exons: Dict[str, CoverageRegionDoc] = Field(default_factory=dict)
    CDS: Dict[str, CoverageRegionDoc] = Field(default_factory=dict)
    probes: Dict[str, ProbeRegionDoc] = Field(default_factory=dict)


class PanelCovDoc(_DocBase):
    """Per-gene coverage records for a panel and sample."""

    genes: Dict[str, GeneCoverageDoc] = Field(default_factory=dict)
    SAMPLE_ID: str
    sample: str


class GroupCoverageDoc(_DocBase):
    """Per-gene coverage records for an assay group and sample."""

    genes: Dict[str, GeneCoverageDoc] = Field(default_factory=dict)
    SAMPLE_ID: str
    sample: str
