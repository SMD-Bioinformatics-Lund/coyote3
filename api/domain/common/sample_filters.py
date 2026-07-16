"""Sample-level filter and file-shape helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DNA_SNV_FILTER_KEYS = {
    "max_freq",
    "min_freq",
    "max_control_freq",
    "max_popfreq",
    "min_depth",
    "min_alt_reads",
    "vep_consequences",
    "snvlists",
    "adhoc_genes",
}
DNA_CNV_FILTER_KEYS = {
    "min_cnv_size",
    "max_cnv_size",
    "cnv_loss_cutoff",
    "cnv_gain_cutoff",
    "cnveffects",
    "cnvlists",
    "adhoc_genes",
}
DNA_COVERAGE_FILTER_KEYS = {"warn_cov", "error_cov"}
RNA_FUSION_FILTER_KEYS = {
    "fusion_callers",
    "fusion_effects",
    "fusionlists",
    "min_spanning_pairs",
    "min_spanning_reads",
    "adhoc_genes",
}


def sample_filters_from_aspc_filters(
    filters: dict[str, Any] | None, omics_layer: str
) -> dict[str, Any]:
    """Convert ASPC filter defaults into the persisted sample filter namespace."""
    source = deepcopy(filters or {})
    if str(omics_layer or "").strip().lower() == "rna":
        return {"fusion": _pick(source, RNA_FUSION_FILTER_KEYS)}
    return {
        "snv": _pick(source, DNA_SNV_FILTER_KEYS),
        "cnv": _pick(source, DNA_CNV_FILTER_KEYS),
        "coverage": _pick(source, DNA_COVERAGE_FILTER_KEYS),
    }


def sample_filter_section(
    filters: dict[str, Any] | None,
    section: str,
    *,
    omics_layer: str = "dna",
) -> dict[str, Any]:
    """Return one canonical sample filter section."""
    normalized = normalize_sample_filters(filters, omics_layer=omics_layer)
    value = normalized.get(section)
    return deepcopy(value) if isinstance(value, dict) else {}


def canonical_dna_filter_section(filters: dict[str, Any] | None, section: str) -> dict[str, Any]:
    """Return one DNA filter section with only keys valid for that section."""
    source = deepcopy(filters or {})
    if not isinstance(source, dict):
        source = {}
    keys = {
        "snv": DNA_SNV_FILTER_KEYS,
        "cnv": DNA_CNV_FILTER_KEYS,
        "coverage": DNA_COVERAGE_FILTER_KEYS,
    }.get(section)
    if keys is None:
        return {}
    return _pick(source, keys)


def merge_filter_defaults(
    filters: dict[str, Any] | None,
    defaults: dict[str, Any] | None,
    *,
    omics_layer: str,
) -> dict[str, Any]:
    """Merge canonical sample filters with ASPC defaults for required empty sections."""
    normalized = normalize_sample_filters(filters, omics_layer=omics_layer)
    default_sections = sample_filters_from_aspc_filters(defaults, omics_layer)
    layer = str(omics_layer or "").strip().lower()
    sections = ("fusion",) if layer == "rna" else ("snv", "cnv", "coverage")
    list_keys = {
        "snv": ("vep_consequences", "snvlists"),
        "cnv": ("cnveffects", "cnvlists"),
        "fusion": ("fusion_callers", "fusion_effects", "fusionlists"),
    }
    for section in sections:
        current_section = normalized.setdefault(section, {})
        default_section = default_sections.get(section) or {}
        for key, value in default_section.items():
            if key not in current_section:
                current_section[key] = deepcopy(value)
                continue
            if key in list_keys.get(section, ()) and current_section.get(key) == [] and value:
                current_section[key] = deepcopy(value)
    return normalized


def merged_dna_variant_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Return flat SNV+coverage settings for legacy query builders."""
    normalized = normalize_sample_filters(filters, omics_layer="dna")
    merged = {}
    merged.update(normalized.get("snv") or {})
    merged.update(normalized.get("coverage") or {})
    return merged


def merged_dna_cnv_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Return flat CNV+coverage settings for CNV query builders."""
    normalized = normalize_sample_filters(filters, omics_layer="dna")
    merged = {}
    merged.update(normalized.get("cnv") or {})
    merged.update(normalized.get("coverage") or {})
    return merged


def normalize_sample_filters(
    filters: dict[str, Any] | None,
    *,
    omics_layer: str,
) -> dict[str, Any]:
    """Normalize persisted or incoming sample filters to the canonical sectioned shape."""
    source = deepcopy(filters or {})
    if not isinstance(source, dict):
        source = {}

    layer = str(omics_layer or "").strip().lower()
    if layer == "rna":
        if isinstance(source.get("fusion"), dict):
            return {"fusion": _pick(source["fusion"], RNA_FUSION_FILTER_KEYS)}
        return sample_filters_from_aspc_filters(source, "rna")

    if any(isinstance(source.get(section), dict) for section in ("snv", "cnv", "coverage")):
        return {
            "snv": canonical_dna_filter_section(source.get("snv") or {}, "snv"),
            "cnv": canonical_dna_filter_section(source.get("cnv") or {}, "cnv"),
            "coverage": canonical_dna_filter_section(source.get("coverage") or {}, "coverage"),
        }
    return sample_filters_from_aspc_filters(source, "dna")


def _pick(source: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: deepcopy(source[key]) for key in keys if key in source}
