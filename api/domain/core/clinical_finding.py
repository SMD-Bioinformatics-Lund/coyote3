"""Canonical display and deduplication helpers for clinical findings."""

from __future__ import annotations

import re
from typing import Any

NOMENCLATURE_ANALYSIS_TYPES: dict[str, str] = {
    "p": "SNV",
    "c": "SNV",
    "g": "SNV",
    "cn": "CNV",
    "f": "FUSION",
    "t": "TRANSLOCATION",
}


def finding_analysis_type(document: dict[str, Any]) -> str:
    """Return the normalized analysis type for an annotation or report snapshot."""
    explicit = document.get("analysis_type")
    if explicit:
        return str(explicit).strip().upper()
    nomenclature_type = NOMENCLATURE_ANALYSIS_TYPES.get(
        str(document.get("nomenclature") or "").strip().lower()
    )
    if nomenclature_type:
        return nomenclature_type
    return (
        str(document.get("finding_type") or document.get("var_type") or "FINDING").strip().upper()
    )


def finding_genes(document: dict[str, Any]) -> list[str]:
    """Return the unique genes involved in a finding in stable display order."""
    values: list[Any] = []
    stored_genes = document.get("genes")
    if isinstance(stored_genes, list):
        values.extend(stored_genes)
    gene = document.get("gene")
    if gene:
        values.extend(re.split(r"\s*(?:::|,|&|\|)\s*", str(gene)))
    values.extend((document.get("gene1"), document.get("gene2")))
    return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))


def finding_identity(document: dict[str, Any]) -> str:
    """Return the nomenclature-aware human-readable identity for a finding."""
    nomenclature = str(document.get("nomenclature") or "").strip().lower()
    preferred_fields = {
        "p": ("hgvsp", "variant", "genomic", "simple_id"),
        "c": ("hgvsc", "variant", "genomic", "simple_id"),
        "g": ("genomic", "variant", "simple_id"),
        "cn": ("variant", "cnv", "simple_id"),
        "f": ("variant", "fusion", "simple_id"),
        "t": ("variant", "translocation", "simple_id"),
    }.get(nomenclature, ())
    fallback_fields = (
        "variant",
        "hgvsp",
        "hgvsc",
        "genomic",
        "simple_id",
        "simple_id_hash",
    )
    for field in (*preferred_fields, *fallback_fields):
        value = str(document.get(field) or "").strip()
        if value:
            return value
    genes = finding_genes(document)
    return "::".join(genes) if genes else "unknown"


def finding_dedup_key(document: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    """Return a collision-resistant key across all supported finding types."""
    return (
        finding_analysis_type(document),
        finding_identity(document),
        tuple(finding_genes(document)),
    )


def finding_display_fields(document: dict[str, Any]) -> dict[str, Any]:
    """Return normalized fields consumed by common search and cohort clients."""
    return {
        "analysis_type": finding_analysis_type(document),
        "genes": finding_genes(document),
        "identity": finding_identity(document),
    }


__all__ = [
    "NOMENCLATURE_ANALYSIS_TYPES",
    "finding_analysis_type",
    "finding_dedup_key",
    "finding_display_fields",
    "finding_genes",
    "finding_identity",
]
