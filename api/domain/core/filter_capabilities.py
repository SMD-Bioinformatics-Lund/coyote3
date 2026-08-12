"""Application-owned clinical filter capabilities.

This module is deliberately code-owned.  It defines the supported analytical
model, while a centre-owned TOML file maps those analysis types to its local
file names.  A deployment may rename an input file, but it may not invent a
new clinical filter field or enable an unsupported germline workflow.
"""

from __future__ import annotations

from typing import Any

from api.contracts.schemas.filter_profiles import (
    CnvFiltersDoc,
    CoverageFiltersDoc,
    FusionFiltersDoc,
    GermlineSnvFiltersDoc,
    SnvFiltersDoc,
    TranslocationFiltersDoc,
)

ANALYSIS_INTENT_OPTIONS: tuple[str, ...] = ("somatic", "germline")
GERMLINE_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = ("SNV",)

FILTER_PROFILE_MODELS: dict[tuple[str, str, str], type[Any]] = {
    ("dna", "somatic", "snv"): SnvFiltersDoc,
    ("dna", "somatic", "cnv"): CnvFiltersDoc,
    ("dna", "somatic", "translocation"): TranslocationFiltersDoc,
    ("dna", "somatic", "coverage"): CoverageFiltersDoc,
    ("dna", "germline", "snv"): GermlineSnvFiltersDoc,
    ("rna", "somatic", "fusion"): FusionFiltersDoc,
}

ANALYSIS_FILTER_SECTIONS: dict[tuple[str, str], str] = {
    ("dna", "SNV"): "snv",
    ("dna", "CNV"): "cnv",
    ("dna", "TRANSLOCATION"): "translocation",
    ("dna", "COVERAGE"): "coverage",
    ("rna", "FUSION"): "fusion",
}


def filter_section_for_analysis(*, omics_layer: str, analysis_type: str) -> str | None:
    """Return the persisted filter section for one supported analysis type."""
    return ANALYSIS_FILTER_SECTIONS.get(
        (str(omics_layer).strip().lower(), str(analysis_type).strip().upper())
    )


def filter_keys(*, omics_layer: str, intent: str, section: str) -> frozenset[str]:
    """Return the immutable accepted field names for one filter profile."""
    model = FILTER_PROFILE_MODELS.get(
        (
            str(omics_layer).strip().lower(),
            str(intent).strip().lower(),
            str(section).strip().lower(),
        )
    )
    if model is None:
        return frozenset()
    return frozenset(model.model_fields)


def select_filter_values(
    values: dict[str, Any] | None, *, omics_layer: str, intent: str, section: str
) -> dict[str, Any]:
    """Retain only values accepted by the specified frozen profile."""
    source = values if isinstance(values, dict) else {}
    allowed = filter_keys(omics_layer=omics_layer, intent=intent, section=section)
    return {key: value for key, value in source.items() if key in allowed}
