"""Common DNA variant helper utilities."""

from collections import defaultdict
from typing import Any

from coyote3.domain.annotation_identity import (
    NOMENCLATURE_FIELDS,
    annotation_identity_fields,
    primary_small_variant_identity,
)


def format_pon(variant: dict[str, Any]) -> defaultdict[str, dict[str, Any]]:
    """
    Format PON keys from variant INFO into nested map by class and numeric type.
    """
    pon: defaultdict[str, dict[str, Any]] = defaultdict(dict)
    for i in variant["INFO"]:
        if "PON_" in i:
            part = i.split("_")
            if len(part) == 3:
                numtype = part[1]
                vc = part[2]
                pon[vc][numtype] = variant["INFO"][i]
    return pon


def get_variant_nomenclature(data: dict[str, Any]) -> tuple[str, str]:
    """Resolve structural identity or the preferred protein, coding or genomic identity."""
    nomenclature = str(data.get("nomenclature") or "").strip().lower()
    variant = str(data.get("variant") or "").strip()
    if nomenclature not in NOMENCLATURE_FIELDS:
        allowed = ", ".join(sorted(NOMENCLATURE_FIELDS))
        raise ValueError(f"nomenclature must be one of: {allowed}")
    if not variant:
        raise ValueError("variant is required")
    if nomenclature in {"p", "c", "g"}:
        identities = annotation_identity_fields(
            variant=variant, nomenclature=nomenclature, source=data
        )
        return primary_small_variant_identity(identities)
    return nomenclature, variant
