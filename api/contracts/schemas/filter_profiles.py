"""Typed, intent-aware clinical filter profiles.

The filter vocabulary is owned by the application.  ASPCs and samples may set
values only for the groups represented here; arbitrary keys are rejected.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from api.contracts.schemas.base import _StrictDocBase


class SnvFiltersDoc(_StrictDocBase):
    max_freq: float = Field(default=1.0, ge=0.0, le=1.0)
    min_freq: float = Field(default=0.0, ge=0.0, le=1.0)
    max_control_freq: float = Field(default=0.05, ge=0.0, le=0.5)
    max_popfreq: float = Field(default=0.05, ge=0.0, le=0.5)
    min_depth: int = Field(default=100, ge=0)
    min_alt_reads: int = Field(default=5, ge=0)
    vep_consequences: list[str] = Field(default_factory=list)
    snvlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_read_depth(self) -> "SnvFiltersDoc":
        if self.min_depth < self.min_alt_reads:
            raise ValueError("min_depth must be greater than or equal to min_alt_reads")
        return self


class GermlineSnvFiltersDoc(_StrictDocBase):
    """SNV filter profile for constitutional review.

    ``max_control_freq`` is intentionally absent. A tumour-normal exclusion
    threshold is not a germline filtering concept.
    """

    max_freq: float = Field(default=1.0, ge=0.0, le=1.0)
    min_freq: float = Field(default=0.0, ge=0.0, le=1.0)
    max_popfreq: float = Field(default=0.05, ge=0.0, le=0.5)
    min_depth: int = Field(default=100, ge=0)
    min_alt_reads: int = Field(default=5, ge=0)
    vep_consequences: list[str] = Field(default_factory=list)
    snvlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_read_depth(self) -> "GermlineSnvFiltersDoc":
        if self.min_depth < self.min_alt_reads:
            raise ValueError("min_depth must be greater than or equal to min_alt_reads")
        return self


class CnvFiltersDoc(_StrictDocBase):
    min_cnv_size: int = Field(default=100, ge=0)
    max_cnv_size: int = Field(default=50_000_000, ge=0)
    cnv_loss_cutoff: float = Field(default=-0.3)
    cnv_gain_cutoff: float = Field(default=0.3)
    cnveffects: list[str] = Field(default_factory=lambda: ["gain", "loss"])
    cnvlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "CnvFiltersDoc":
        if self.min_cnv_size > self.max_cnv_size:
            raise ValueError("min_cnv_size must be less than or equal to max_cnv_size")
        if self.cnv_loss_cutoff >= self.cnv_gain_cutoff:
            raise ValueError("cnv_loss_cutoff must be less than cnv_gain_cutoff")
        invalid = [effect for effect in self.cnveffects if effect not in {"gain", "loss"}]
        if invalid:
            raise ValueError("cnveffects may contain only gain and loss")
        return self


class CoverageFiltersDoc(_StrictDocBase):
    warn_cov: int = Field(default=100, ge=0)
    error_cov: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "CoverageFiltersDoc":
        if self.error_cov > self.warn_cov:
            raise ValueError("error_cov must be less than or equal to warn_cov")
        return self


class FusionFiltersDoc(_StrictDocBase):
    fusion_callers: list[str] = Field(default_factory=list)
    fusion_effects: list[str] = Field(default_factory=list)
    fusionlists: list[str] = Field(default_factory=list)
    min_spanning_pairs: int = Field(default=0, ge=0)
    min_spanning_reads: int = Field(default=0, ge=0)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)


class TranslocationFiltersDoc(_StrictDocBase):
    """Gene scope for DNA fusion/translocation review.

    DNA translocations reuse fusion-compatible ISGLs because both represent
    gene-pair findings. RNA-only spanning-read and caller thresholds do not
    apply to the DNA VCF contract.
    """

    fusionlists: list[str] = Field(default_factory=list)
    adhoc_genes: dict[str, Any] = Field(default_factory=dict)


class SomaticDnaFiltersDoc(_StrictDocBase):
    snv: SnvFiltersDoc | None = None
    cnv: CnvFiltersDoc | None = None
    translocation: TranslocationFiltersDoc | None = None
    coverage: CoverageFiltersDoc | None = None


class GermlineDnaFiltersDoc(_StrictDocBase):
    """Current germline capability: SNV only."""

    snv: GermlineSnvFiltersDoc | None = None


class DnaFilterProfilesDoc(_StrictDocBase):
    somatic: SomaticDnaFiltersDoc | None = None
    germline: GermlineDnaFiltersDoc | None = None


class SomaticRnaFiltersDoc(_StrictDocBase):
    fusion: FusionFiltersDoc | None = None


class RnaFilterProfilesDoc(_StrictDocBase):
    somatic: SomaticRnaFiltersDoc | None = None
