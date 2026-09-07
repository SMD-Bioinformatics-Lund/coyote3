"""Canonical variant identity helpers for DNA small variants."""

from __future__ import annotations

from hashlib import md5
from typing import Any


def _norm_text(value: Any) -> str:
    """Normalize arbitrary value to stripped text."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_chrom(chrom: Any) -> str:
    """Normalize chromosome representation to stable tokens (no `chr` prefix)."""
    value = _norm_text(chrom)
    if not value:
        return ""
    lower = value.lower()
    if lower.startswith("chr"):
        value = value[3:]
    value = value.strip()
    upper = value.upper()
    if upper in {"M", "MT"}:
        return "MT"
    return upper


def normalize_pos(pos: Any) -> str:
    """Normalize genomic position to canonical integer string when possible."""
    raw = _norm_text(pos)
    if raw == "":
        return ""
    try:
        return str(int(raw))
    except (TypeError, ValueError):
        return raw


def normalize_allele(allele: Any) -> str:
    """Normalize allele text for stable identity hashing."""
    return _norm_text(allele).upper()


def build_simple_id(chrom: Any, pos: Any, ref: Any, alt: Any) -> str:
    """Build canonical simple variant identifier."""
    return "_".join(
        (
            normalize_chrom(chrom),
            normalize_pos(pos),
            normalize_allele(ref),
            normalize_allele(alt),
        )
    )


def normalize_simple_id(simple_id: Any) -> str:
    """Normalize an existing simple_id into canonical format."""
    raw = _norm_text(simple_id)
    if not raw:
        return ""
    parts = raw.split("_", 3)
    if len(parts) != 4:
        return raw
    return build_simple_id(parts[0], parts[1], parts[2], parts[3])


def build_simple_id_hash_from_simple_id(simple_id: Any) -> str:
    """Build deterministic MD5 hex digest from canonical simple_id."""
    normalized = normalize_simple_id(simple_id)
    return md5(normalized.encode("utf-8")).hexdigest()


def ensure_variant_identity_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Populate/normalize simple_id and simple_id_hash on a variant-like document."""
    normalized_simple = normalize_simple_id(doc.get("simple_id"))
    if not normalized_simple:
        normalized_simple = build_simple_id(
            doc.get("CHROM"), doc.get("POS"), doc.get("REF"), doc.get("ALT")
        )

    out = dict(doc)
    out["simple_id"] = normalized_simple
    out["simple_id_hash"] = build_simple_id_hash_from_simple_id(normalized_simple)
    return out
