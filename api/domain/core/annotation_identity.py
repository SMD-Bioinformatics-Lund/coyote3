"""Canonical identity fields for clinical annotation documents."""

from __future__ import annotations

import re
from typing import Any, Mapping

from api.domain.core.dna.variant_identity import (
    build_simple_id,
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)

ANNOTATION_IDENTITY_FIELDS: tuple[str, ...] = (
    "hgvsp",
    "hgvsc",
    "genomic",
    "genomic_hash",
    "cnv",
    "fusion",
    "translocation",
)

NOMENCLATURE_IDENTITY_FIELD: dict[str, str] = {
    "p": "hgvsp",
    "c": "hgvsc",
    "g": "genomic",
    "cn": "cnv",
    "f": "fusion",
    "t": "translocation",
}

_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "hgvsp": ("hgvsp", "HGVSp", "var_p"),
    "hgvsc": ("hgvsc", "HGVSc", "var_c"),
    # Variant documents call this identity simple_id. Annotation documents
    # expose it as genomic so the persistence contract describes its meaning.
    "genomic": ("simple_id", "genomic", "var_g"),
    "cnv": ("cnv", "cnvvar"),
    "fusion": ("fusion", "fusionpoints"),
    "translocation": ("translocation", "translocpoints"),
}


def _text(value: Any) -> str | None:
    """Return the first non-empty scalar value as text."""
    if isinstance(value, (list, tuple)):
        for item in value:
            normalized = _text(item)
            if normalized:
                return normalized
        return None
    if value is None or isinstance(value, (dict, set)):
        return None
    normalized = str(value).strip()
    return normalized or None


def _selected_csq(source: Mapping[str, Any]) -> Mapping[str, Any]:
    info = source.get("INFO")
    if not isinstance(info, Mapping):
        return {}
    selected = info.get("selected_CSQ")
    return selected if isinstance(selected, Mapping) else {}


def _candidate(source: Mapping[str, Any], field: str) -> str | None:
    selected_csq = _selected_csq(source)
    for key in _SOURCE_KEYS[field]:
        for container in (source, selected_csq):
            value = _text(container.get(key))
            if value:
                return value
    return None


def _canonical_genomic(source: Mapping[str, Any], fallback: str | None) -> str | None:
    simple_id = _candidate(source, "genomic") or fallback
    if not simple_id:
        chromosome = source.get("CHROM")
        position = source.get("POS")
        reference = source.get("REF")
        alternate = source.get("ALT")
        if all(value not in (None, "") for value in (chromosome, position, reference, alternate)):
            return build_simple_id(chromosome, position, reference, alternate)
        return None

    normalized = normalize_simple_id(simple_id)
    if normalized != simple_id or simple_id.count("_") >= 3:
        return normalized

    match = re.fullmatch(r"([^:]+):([^:]+):([^/]+)/(.+)", simple_id)
    if match:
        return build_simple_id(*match.groups())
    return simple_id


def annotation_identity_fields(
    *,
    variant: Any,
    nomenclature: Any,
    source: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Collect every available flat identity for an annotation.

    ``variant`` remains the primary display identity. The returned keys are
    secondary, queryable representations of the same finding.
    """
    source = source or {}
    identities = {
        field: value
        for field in ANNOTATION_IDENTITY_FIELDS
        if field not in {"genomic", "genomic_hash"}
        if (value := _candidate(source, field)) is not None
    }

    primary = _text(variant)
    primary_field = NOMENCLATURE_IDENTITY_FIELD.get(str(nomenclature or "").strip().lower())
    genomic = _canonical_genomic(source, primary if primary_field == "genomic" else None)
    if genomic:
        identities["genomic"] = genomic
    if primary and primary_field and primary_field != "genomic":
        identities.setdefault(primary_field, primary)

    if genomic:
        identities["genomic_hash"] = build_simple_id_hash_from_simple_id(genomic)

    return identities


def enrich_annotation_identity(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return an annotation copy populated with canonical identity fields."""
    enriched = dict(document)
    enriched.pop("simple_id", None)
    enriched.pop("simple_id_hash", None)
    nested_source = document.get("variant_data")
    source = {
        **(dict(nested_source) if isinstance(nested_source, Mapping) else {}),
        **document,
    }
    enriched.update(
        annotation_identity_fields(
            variant=document.get("variant"),
            nomenclature=document.get("nomenclature"),
            source=source,
        )
    )
    return enriched


__all__ = [
    "ANNOTATION_IDENTITY_FIELDS",
    "NOMENCLATURE_IDENTITY_FIELD",
    "annotation_identity_fields",
    "enrich_annotation_identity",
]
