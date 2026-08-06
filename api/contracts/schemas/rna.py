"""RNA-centric document contracts."""

from __future__ import annotations

from typing import Dict, List

from pydantic import Field, field_validator

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.contracts.schemas.base import (
    _DocBase,
    _StrictDocBase,
    model_validator,
)


class RnaFiltersDoc(_StrictDocBase):
    fusion_callers: list[str] = Field(default_factory=list)
    fusion_descriptions: list[str] = Field(default_factory=list)
    fusion_effects: list[str] = Field(default_factory=list)
    fusionlists: list[str] = Field(default_factory=list)
    min_spanning_pairs: int = 0
    min_spanning_reads: int = 0

    @field_validator("fusion_callers", mode="before")
    @classmethod
    def normalize_fusion_callers(cls, value):
        return CLINICAL_VOCABULARY.normalize_fusion_callers(value or [])

    @model_validator(mode="before")
    @classmethod
    def _apply_field_defaults_for_unset_values(cls, data):
        """Treat null and empty list filter values as unset so defaults apply."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        for key in {"min_spanning_pairs", "min_spanning_reads"}:
            if key in normalized and normalized[key] is None:
                normalized.pop(key, None)
        for key in {"fusion_callers", "fusion_descriptions", "fusion_effects", "fusionlists"}:
            if key in normalized and (
                normalized[key] is None
                or (isinstance(normalized[key], list) and len(normalized[key]) == 0)
            ):
                normalized.pop(key, None)
        return normalized


class FusionCallDoc(_DocBase):
    selected: int
    longestanchor: int | str
    caller: str
    spanpairs: int
    spanreads: int
    breakpoint1: str
    breakpoint2: str
    effect: str
    commonreads: int
    desc: str

    @field_validator("caller", mode="before")
    @classmethod
    def normalize_caller(cls, value):
        callers = CLINICAL_VOCABULARY.normalize_fusion_callers([value])
        return callers[0]

    @field_validator("longestanchor", mode="before")
    @classmethod
    def normalize_longest_anchor(cls, v):
        """Preserve bounded STAR-Fusion anchors while typing numeric anchors."""
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            return int(v)
        return v

    @field_validator("commonreads", mode="before")
    @classmethod
    def convert_common_reads_to_int(cls, v):
        if isinstance(v, str):
            return int(v)
        return v


class FusionsDoc(_DocBase):
    SAMPLE_ID: str

    gene1: str
    gene2: str
    genes: str
    fp: str | bool = ""
    irrelevant: str | bool = ""
    interesting: str | bool = ""
    blacklisted: str | bool = ""

    calls: List[FusionCallDoc]


class ExpressionSampleEntryDoc(_DocBase):
    hgnc_symbol: str
    ensembl_gene_id: str
    sample_expression: float
    reference_sd: float
    reference_mean: float
    reference_median: float
    reference_mean_mod: float
    sample_mod: float
    z: float


class ExpressionReferenceEntryDoc(_DocBase):
    hgnc_symbol: str
    ensembl_gene_id: str
    reference_sd: float
    reference_mean: float
    reference_median: float
    quant_values: dict[str, float]

    @model_validator(mode="before")
    @classmethod
    def _split_dynamic_quant_values(cls, data: dict) -> dict:
        fixed_fields = {
            "hgnc_symbol",
            "ensembl_gene_id",
            "reference_sd",
            "reference_mean",
            "reference_median",
        }

        quant_values = {key: float(value) for key, value in data.items() if key not in fixed_fields}

        cleaned = {key: data[key] for key in fixed_fields if key in data}
        cleaned["quant_values"] = quant_values
        return cleaned


class RnaExpressionDoc(_DocBase):
    sample: list[ExpressionSampleEntryDoc]
    reference: list[ExpressionReferenceEntryDoc]
    expression_version: str
    SAMPLE_ID: str


class ClassifierResultDoc(_DocBase):
    class_: str = Field(alias="class")
    score: float
    true: int
    total: int

    @model_validator(mode="after")
    def _validate_counts(self) -> "ClassifierResultDoc":
        if self.true > self.total:
            raise ValueError("true cannot be greater than total")
        return self


class RnaClassificationDoc(_DocBase):
    classifier_results: list[ClassifierResultDoc]
    classifier_version: str
    SAMPLE_ID: str


class RnaQcDoc(_DocBase):
    tot_reads: int
    mapped_pct: float
    multimap_pct: float
    mismatch_pct: float

    canon_splice: int
    non_canon_splice: int
    splice_ratio: int

    genebody_cov: List[int]
    genebody_cov_slope: float

    provider_genotypes: Dict[str, str]
    provider_called_genotypes: int

    flendist: int

    sample_id: str
    SAMPLE_ID: str

    @field_validator("mapped_pct", "multimap_pct", "mismatch_pct")
    @classmethod
    def validate_percentage(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("Percentage must be between 0 and 100")
        return v

    @field_validator("provider_genotypes")
    @classmethod
    def validate_genotypes(cls, v):
        for k, val in v.items():
            if not isinstance(val, str):
                raise ValueError(f"Invalid genotype for {k}")
        return v
