"""Common DNA variant helper utilities."""

from collections import defaultdict

from api.domain.core.annotation_identity import NOMENCLATURE_FIELDS


def format_pon(variant: dict) -> defaultdict:
    """
    Format PON keys from variant INFO into nested map by class and numeric type.
    """
    pon = defaultdict(dict)
    for i in variant["INFO"]:
        if "PON_" in i:
            part = i.split("_")
            if len(part) == 3:
                numtype = part[1]
                vc = part[2]
                pon[vc][numtype] = variant["INFO"][i]
    return pon


def get_variant_nomenclature(data: dict) -> tuple[str, str]:
    """Return the explicit canonical annotation identity from an API payload."""
    nomenclature = str(data.get("nomenclature") or "").strip().lower()
    variant = str(data.get("variant") or "").strip()
    if nomenclature not in NOMENCLATURE_FIELDS:
        allowed = ", ".join(sorted(NOMENCLATURE_FIELDS))
        raise ValueError(f"nomenclature must be one of: {allowed}")
    if not variant:
        raise ValueError("variant is required")
    return nomenclature, variant
