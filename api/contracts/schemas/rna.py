"""RNA-centric document contracts."""

from __future__ import annotations

from typing import Dict, List

from pydantic import Field

from api.contracts.schemas.base import (
    _DocBase,
    _StrictDocBase,
    field_validator,
    model_validator,
)


class RnaFiltersDoc(_StrictDocBase):
    fusion_callers: list[str] = Field(default_factory=list)
    fusion_effects: list[str] = Field(default_factory=list)
    fusion_genelists: list[str] = Field(default_factory=list)
    min_spanning_pairs: int = 0
    min_spanning_reads: int = 0


class FusionCallDoc(_DocBase):
    selected: int
    longestanchor: int
    caller: str
    spanpairs: int
    spanreads: int
    breakpoint1: str
    breakpoint2: str
    effect: str
    commonreads: int
    desc: str

    @field_validator("longestanchor", "commonreads", mode="before")
    @classmethod
    def convert_str_to_int(cls, v):
        # Handles "30" → 30
        if isinstance(v, str):
            return int(v)
        return v


class FusionsDoc(_DocBase):
    SAMPLE_ID: str

    gene1: str
    gene2: str
    genes: str

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
