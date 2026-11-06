"""
Common filter coercion/normalization helpers for workflow services.
"""

from typing import Any


def coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    """Parse a nonnegative count, falling back for invalid or overflowing input.

    Args:
        value: Form or persisted value accepted by int.
        default: Value returned for negative or unparseable counts.

    Returns:
        Parsed count or the supplied default.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_rna_filter_keys(filters: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize RNA filters and map form-style prefixed keys to canonical lists.
    """
    normalized = dict(filters or {})
    _strip_form_meta_keys(normalized)
    _fold_prefixed_flags(
        normalized,
        {
            "fusioncaller_": "fusion_callers",
            "fusiondescription_": "fusion_descriptions",
            "fusioneffect_": "fusion_effects",
            "fusionlist_": "fusionlists",
        },
    )
    min_reads = normalized.get("min_spanning_reads", 0)
    min_pairs = normalized.get("min_spanning_pairs", 0)
    normalized["min_spanning_reads"] = coerce_nonnegative_int(min_reads, default=0)
    normalized["min_spanning_pairs"] = coerce_nonnegative_int(min_pairs, default=0)
    return normalized


def normalize_dna_filter_keys(filters: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize DNA filters and map form-style prefixed keys to canonical lists.
    """
    normalized = dict(filters or {})
    _strip_form_meta_keys(normalized)
    _fold_prefixed_flags(
        normalized,
        {
            "vep_": "vep_consequences",
            "snvlist_": "snvlists",
            "cnvlist_": "cnvlists",
            "cnveffect_": "cnveffects",
        },
    )
    return normalized


def _strip_form_meta_keys(filters: dict[str, Any]) -> None:
    """Remove form-only metadata keys from incoming filter payload."""
    for key in ("csrf_token", "submit", "reset"):
        filters.pop(key, None)


def _fold_prefixed_flags(filters: dict[str, Any], prefix_map: dict[str, str]) -> None:
    """Replace canonical selections when prefixed checkboxes were submitted.

    Args:
        filters: Mutable payload; consumed checkbox keys are removed. Explicitly
            unchecked groups clear the existing canonical selection.
        prefix_map: Form prefixes mapped to their canonical list keys.
    """
    for prefix, canonical_key in prefix_map.items():
        selected: list[str] = []
        supplied = False
        for key, value in list(filters.items()):
            if not str(key).startswith(prefix):
                continue
            supplied = True
            if _is_truthy_flag(value):
                selected.append(str(key).replace(prefix, "", 1))
            filters.pop(key, None)
        if supplied:
            filters[canonical_key] = selected
        elif canonical_key not in filters:
            filters[canonical_key] = []


def _is_truthy_flag(value: Any) -> bool:
    """Is truthy flag.

    Args:
            value: Value.

    Returns:
            The  is truthy flag result.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    value_str = str(value).strip().lower()
    return value_str in {"1", "true", "on", "yes"}
