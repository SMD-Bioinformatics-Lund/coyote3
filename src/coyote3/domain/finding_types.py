"""Canonical finding family identifiers and the existing accepted input spellings."""


def normalize_finding_kind(resource_type: str | None) -> str:
    """Normalize an existing finding-family spelling without accepting new resource kinds.

    Args:
        resource_type: Existing API spelling; None or an empty value selects small_variant.

    Returns:
        Canonical family identifier, or the normalized unknown value for existing validation.
    """
    value = str(resource_type or "small_variant").strip().lower().replace("-", "_")
    return {
        "variant": "small_variant",
        "snv": "small_variant",
        "small_variants": "small_variant",
        "fusion": "fusion",
        "cnv": "cnv",
        "transloc": "translocation",
        "translocation": "translocation",
    }.get(value, value)
