"""Intent-aware sample filter profile helpers.

Persisted ASPC and sample filters use one canonical shape::

    filters.somatic.<analysis>
    filters.germline.snv

The helpers below expose a selected profile to query services without allowing
query code to redefine the persisted contract.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.schemas.filter_profiles import (
    DnaFilterProfilesDoc,
    RnaFilterProfilesDoc,
)
from api.domain.core.filter_capabilities import (
    ANALYSIS_INTENT_OPTIONS,
    GERMLINE_ANALYSIS_TYPE_OPTIONS,
)

DNA_FILTER_SECTIONS = ("snv", "cnv", "coverage")
RNA_FILTER_SECTIONS = ("fusion",)
VALID_INTENTS = ANALYSIS_INTENT_OPTIONS


def _merge_missing_values(current: Any, defaults: Any) -> Any:
    """Return current values completed with any missing nested defaults."""
    if not isinstance(current, dict) or not isinstance(defaults, dict):
        return deepcopy(current)
    merged = deepcopy(current)
    for key, default_value in defaults.items():
        if key not in merged:
            merged[key] = deepcopy(default_value)
        elif isinstance(merged[key], dict) and isinstance(default_value, dict):
            merged[key] = _merge_missing_values(merged[key], default_value)
    return merged


def normalize_analysis_intents(value: Any, *, omics_layer: str) -> list[str]:
    """Normalize supported sample/ASPC analysis intents."""
    values = value if isinstance(value, list) else [value]
    intents = list(
        dict.fromkeys(str(item or "").strip().lower() for item in values if str(item or "").strip())
    )
    if not intents:
        return ["somatic"]
    invalid = [intent for intent in intents if intent not in VALID_INTENTS]
    if invalid:
        raise ValueError("analysis_intents may contain only somatic and germline")
    if str(omics_layer or "").strip().lower() != "dna" and "germline" in intents:
        raise ValueError("germline analysis is currently supported only for DNA SNV")
    return intents


def normalize_sample_filters(
    filters: dict[str, Any] | None,
    *,
    omics_layer: str,
    analysis_intents: Any = None,
    canonical: bool = False,
    intent: str = "somatic",
) -> dict[str, Any]:
    """Validate filters and return the canonical object or one selected profile.

    The canonical object is used for ASPC/sample persistence. Query and UI code
    requests an intent profile, which remains a plain section map such as
    ``{"snv": {...}, "cnv": {...}}``.
    """
    layer = str(omics_layer or "dna").strip().lower()
    source = deepcopy(filters or {})
    if not isinstance(source, dict):
        source = {}
    inferred_intents = analysis_intents
    if inferred_intents is None:
        inferred_intents = [key for key in VALID_INTENTS if key in source] or ["somatic"]
    intents = normalize_analysis_intents(inferred_intents, omics_layer=layer)

    model = DnaFilterProfilesDoc if layer == "dna" else RnaFilterProfilesDoc
    validated = model.model_validate(source).model_dump(exclude_none=True)
    _validate_profile_availability(validated, layer=layer, intents=intents)
    if canonical:
        return validated
    selected_intent = str(intent or "somatic").strip().lower()
    if selected_intent not in intents:
        return {}
    profile = validated.get(selected_intent)
    return deepcopy(profile) if isinstance(profile, dict) else {}


def sample_filters_from_aspc_filters(
    filters: dict[str, Any] | None,
    omics_layer: str,
    *,
    analysis_intents: Any = None,
) -> dict[str, Any]:
    """Return the validated full filter snapshot copied from an ASPC."""
    return normalize_sample_filters(
        filters,
        omics_layer=omics_layer,
        analysis_intents=analysis_intents,
        canonical=True,
    )


def sample_filter_section(
    filters: dict[str, Any] | None,
    section: str,
    *,
    omics_layer: str = "dna",
    intent: str = "somatic",
    analysis_intents: Any = None,
) -> dict[str, Any]:
    """Return a validated filter section from one analysis intent."""
    profile = normalize_sample_filters(
        filters,
        omics_layer=omics_layer,
        analysis_intents=analysis_intents,
        intent=intent,
    )
    value = profile.get(section)
    return deepcopy(value) if isinstance(value, dict) else {}


def canonical_dna_filter_section(filters: dict[str, Any] | None, section: str) -> dict[str, Any]:
    """Validate one DNA somatic filter section against the frozen contract."""
    profile = normalize_sample_filters(
        {"somatic": {section: deepcopy(filters or {})}},
        omics_layer="dna",
        canonical=False,
    )
    return deepcopy(profile.get(section) or {})


def merge_filter_defaults(
    filters: dict[str, Any] | None,
    defaults: dict[str, Any] | None,
    *,
    omics_layer: str,
    analysis_intents: Any = None,
) -> dict[str, Any]:
    """Merge only absent canonical groups from the selected ASPC defaults."""
    layer = str(omics_layer or "dna").strip().lower()
    intents = normalize_analysis_intents(analysis_intents, omics_layer=layer)
    current = normalize_sample_filters(
        filters, omics_layer=layer, analysis_intents=intents, canonical=True
    )
    default_profiles = normalize_sample_filters(
        defaults, omics_layer=layer, analysis_intents=intents, canonical=True
    )
    for profile_intent in intents:
        default_profile = default_profiles.get(profile_intent) or {}
        if not default_profile:
            continue
        target_profile = current.setdefault(profile_intent, {})
        for section, default_values in default_profile.items():
            target_profile[section] = _merge_missing_values(
                target_profile.get(section, {}), default_values
            )
    return normalize_sample_filters(
        current, omics_layer=layer, analysis_intents=intents, canonical=True
    )


def merged_dna_variant_filters(
    filters: dict[str, Any] | None, *, intent: str = "somatic", analysis_intents: Any = None
) -> dict[str, Any]:
    """Return SNV and coverage values for the selected DNA intent."""
    profile = normalize_sample_filters(
        filters,
        omics_layer="dna",
        analysis_intents=analysis_intents,
        intent=intent,
    )
    merged = dict(profile.get("snv") or {})
    if intent == "somatic":
        merged.update(profile.get("coverage") or {})
    return merged


def merged_dna_cnv_filters(
    filters: dict[str, Any] | None, *, analysis_intents: Any = None
) -> dict[str, Any]:
    """Return the somatic CNV and coverage values for CNV query builders."""
    profile = normalize_sample_filters(
        filters,
        omics_layer="dna",
        analysis_intents=analysis_intents,
        intent="somatic",
    )
    merged = dict(profile.get("cnv") or {})
    merged.update(profile.get("coverage") or {})
    return merged


def _validate_profile_availability(
    profiles: dict[str, Any], *, layer: str, intents: list[str]
) -> None:
    unexpected_intents = set(profiles) - set(intents)
    if unexpected_intents:
        raise ValueError(
            "filters includes profiles not enabled in analysis_intents: "
            + ", ".join(sorted(unexpected_intents))
        )
    if layer != "dna" and profiles.get("germline"):
        raise ValueError("germline analysis is currently supported only for DNA SNV")
    germline = profiles.get("germline") or {}
    if germline and set(germline) - {section.lower() for section in GERMLINE_ANALYSIS_TYPE_OPTIONS}:
        raise ValueError("germline filters currently support SNV only")
