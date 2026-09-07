"""Canonical identity fields for clinical annotation documents."""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

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
)

ANNOTATION_CONTEXT_FIELDS: tuple[str, ...] = (
    "gene",
    "gene1",
    "gene2",
    "transcript",
)

NOMENCLATURE_FIELDS: dict[str, frozenset[str]] = {
    "p": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "transcript", "variant"}),
    "c": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "transcript", "variant"}),
    "g": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "transcript", "variant"}),
    "cn": frozenset({"variant"}),
    "f": frozenset({"gene1", "gene2", "variant"}),
    "t": frozenset({"gene1", "gene2", "variant"}),
}

NOMENCLATURE_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "p": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "variant"}),
    "c": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "variant"}),
    "g": frozenset({"hgvsp", "hgvsc", "genomic", "genomic_hash", "gene", "variant"}),
    "cn": frozenset({"variant"}),
    "f": frozenset({"gene1", "gene2", "variant"}),
    "t": frozenset({"gene1", "gene2", "variant"}),
}

NOMENCLATURE_IDENTITY_FIELD: dict[str, str] = {
    "p": "hgvsp",
    "c": "hgvsc",
    "g": "genomic",
}

_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "hgvsp": ("hgvsp", "HGVSp"),
    "hgvsc": ("hgvsc", "HGVSc"),
    # Variant documents call this identity simple_id. Annotation documents
    # expose it as genomic so the persistence contract describes its meaning.
    "genomic": ("simple_id", "genomic"),
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
    allowed_fields = NOMENCLATURE_FIELDS.get(str(nomenclature or "").strip().lower(), frozenset())
    identities = {
        field: value
        for field in ANNOTATION_IDENTITY_FIELDS
        if field in allowed_fields
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


def annotation_context_fields(*, nomenclature: Any, source: Mapping[str, Any]) -> dict[str, str]:
    """Return only the gene/transcript context valid for a nomenclature."""
    normalized_nomenclature = str(nomenclature or "").strip().lower()
    allowed_fields = NOMENCLATURE_FIELDS.get(normalized_nomenclature, frozenset())
    return {
        field: value
        for field in ANNOTATION_CONTEXT_FIELDS
        if field in allowed_fields
        if (value := _text(source.get(field))) is not None
    }


def finding_comment_identity(
    finding: Mapping[str, Any],
    finding_type: Literal["small_variant", "cnv", "fusion", "translocation"],
) -> dict[str, Any]:
    """Return the immutable display identity captured with a finding comment."""
    if finding_type == "small_variant":
        selected = _selected_csq(finding)
        source = {
            **dict(finding),
            "hgvsp": selected.get("HGVSp") or finding.get("hgvsp"),
            "hgvsc": selected.get("HGVSc") or finding.get("hgvsc"),
            "gene": selected.get("SYMBOL") or finding.get("gene"),
            "transcript": selected.get("Feature") or finding.get("transcript"),
        }
        genomic = _canonical_genomic(source, None)
        variant = _text(source.get("hgvsp")) or _text(source.get("hgvsc")) or genomic
        nomenclature = "p" if source.get("hgvsp") else "c" if source.get("hgvsc") else "g"
        snapshot: dict[str, Any] = {
            "nomenclature": nomenclature,
            "variant": variant,
            **annotation_context_fields(nomenclature=nomenclature, source=source),
            **annotation_identity_fields(
                variant=variant,
                nomenclature=nomenclature,
                source=source,
            ),
        }
        return {key: value for key, value in snapshot.items() if value not in (None, "")}

    if finding_type == "cnv":
        chromosome = finding.get("chr") or finding.get("CHROM")
        start = finding.get("start") or finding.get("START")
        end = finding.get("end") or finding.get("END")
        variant = (
            f"{chromosome}:{start}-{end}"
            if all(value not in (None, "") for value in (chromosome, start, end))
            else _text(finding.get("variant"))
        )
        return {"nomenclature": "cn", "variant": variant} if variant else {"nomenclature": "cn"}

    genes = finding.get("genes")
    if isinstance(genes, str):
        gene_values = [value.strip() for value in genes.split("^") if value.strip()]
    elif isinstance(genes, (list, tuple)):
        gene_values = [str(value).strip() for value in genes if str(value).strip()]
    else:
        gene_values = []
    gene1 = _text(finding.get("gene1")) or (gene_values[0] if gene_values else None)
    gene2 = _text(finding.get("gene2")) or (gene_values[1] if len(gene_values) > 1 else None)
    nomenclature = "f" if finding_type == "fusion" else "t"
    snapshot = {
        "nomenclature": nomenclature,
        "variant": _text(finding.get("variant")),
        "gene1": gene1,
        "gene2": gene2,
    }
    return {key: value for key, value in snapshot.items() if value not in (None, "")}


def enrich_annotation_identity(
    document: Mapping[str, Any],
    *,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an annotation containing only fields valid for its nomenclature.

    ``document`` is the flat annotation being prepared for persistence.
    ``source`` may contain the current finding payload used to derive equivalent
    identities, but is never copied into the annotation document.
    """
    enriched = dict(document)
    enriched.pop("simple_id", None)
    enriched.pop("simple_id_hash", None)
    identity_source = {**dict(source or {}), **document}
    enriched.update(
        annotation_identity_fields(
            variant=document.get("variant"),
            nomenclature=document.get("nomenclature"),
            source=identity_source,
        )
    )
    enriched.update(
        annotation_context_fields(
            nomenclature=document.get("nomenclature"),
            source=identity_source,
        )
    )

    nomenclature = str(document.get("nomenclature") or "").strip().lower()
    allowed_fields = NOMENCLATURE_FIELDS.get(nomenclature, frozenset())
    for field in (*ANNOTATION_IDENTITY_FIELDS, *ANNOTATION_CONTEXT_FIELDS):
        if field not in allowed_fields:
            enriched.pop(field, None)

    # Required means structurally present. Historical annotations may not have
    # enough retained evidence to recover every equivalent HGVS identity, in
    # which case the related key remains explicitly null instead of being
    # guessed or omitted.
    for field in NOMENCLATURE_REQUIRED_FIELDS.get(nomenclature, frozenset()):
        enriched.setdefault(field, None)

    class_value = enriched.get("class")
    text_value = enriched.get("text")
    if class_value is not None and text_value is None:
        enriched.pop("text", None)
    elif text_value is not None and class_value is None:
        enriched.pop("class", None)
    return enriched


__all__ = [
    "ANNOTATION_IDENTITY_FIELDS",
    "ANNOTATION_CONTEXT_FIELDS",
    "NOMENCLATURE_IDENTITY_FIELD",
    "NOMENCLATURE_FIELDS",
    "NOMENCLATURE_REQUIRED_FIELDS",
    "annotation_context_fields",
    "annotation_identity_fields",
    "enrich_annotation_identity",
    "finding_comment_identity",
]
