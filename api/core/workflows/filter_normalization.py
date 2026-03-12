
"""
Shared filter coercion/normalization helpers for workflow services.
"""

from typing import Any


def coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    """
    Coerce incoming filter values to non-negative integers.
    Handles mixed string/int form and persisted values.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def normalize_rna_filter_keys(filters: dict | None) -> dict:
    """
    Normalize RNA filters and map form-style prefixed keys to canonical lists.
    """
    normalized = dict(filters or {})
    _strip_form_meta_keys(normalized)
    _fold_prefixed_flags(
        normalized,
        {
            "fusioncaller_": "fusion_callers",
            "fusioneffect_": "fusion_effects",
            "fusionlist_": "fusionlists",
        },
    )
    if "fusionlist_id" in normalized:
        fusionlist_id = normalized.pop("fusionlist_id")
        if isinstance(fusionlist_id, str):
            normalized["fusionlists"] = [fusionlist_id] if fusionlist_id else []
        elif isinstance(fusionlist_id, (list, tuple)):
            normalized["fusionlists"] = [str(item) for item in fusionlist_id if str(item)]

    min_reads = normalized.get("min_spanning_reads", normalized.get("spanning_reads", 0))
    min_pairs = normalized.get("min_spanning_pairs", normalized.get("spanning_pairs", 0))
    normalized["min_spanning_reads"] = coerce_nonnegative_int(min_reads, default=0)
    normalized["min_spanning_pairs"] = coerce_nonnegative_int(min_pairs, default=0)
    return normalized


def normalize_dna_filter_keys(filters: dict | None) -> dict:
    """
    Normalize DNA filters and map form-style prefixed keys to canonical lists.
    """
    normalized = dict(filters or {})
    _strip_form_meta_keys(normalized)
    _fold_prefixed_flags(
        normalized,
        {
            "vep_": "vep_consequences",
            "genelist_": "genelists",
            "cnveffect_": "cnveffects",
        },
    )
    return normalized


def _strip_form_meta_keys(filters: dict[str, Any]) -> None:
    """Remove form-only metadata keys from incoming filter payload."""
    for key in ("csrf_token", "submit", "reset"):
        filters.pop(key, None)


def _fold_prefixed_flags(filters: dict[str, Any], prefix_map: dict[str, str]) -> None:
    """
    Fold dynamic prefixed checkbox flags into canonical list-based keys.

    Example:
        {"genelist_PANEL_A": True} -> {"genelists": ["PANEL_A"]}
    """
    for prefix, canonical_key in prefix_map.items():
        selected: list[str] = []
        for key, value in list(filters.items()):
            if not str(key).startswith(prefix):
                continue
            if _is_truthy_flag(value):
                selected.append(str(key).replace(prefix, "", 1))
            filters.pop(key, None)
        if selected:
            filters[canonical_key] = selected
        elif canonical_key not in filters:
            filters[canonical_key] = []


def _is_truthy_flag(value: Any) -> bool:
    """Handle  is truthy flag.

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
