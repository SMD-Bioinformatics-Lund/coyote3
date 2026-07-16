"""Common helpers and constants for admin resource services."""

from __future__ import annotations

from typing import Any

from api.contracts.schemas import normalize_collection_document
from api.domain.common.errors import api_error


def _normalize_asp_category(value: Any) -> str:
    """Normalize ASP category labels to managed DNA/RNA categories."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "DNA",
        "somatic": "DNA",
        "rna": "RNA",
    }
    return mapping.get(raw, str(value or "").strip().upper() or "DNA")


def _normalize_asp_category_doc(value: Any) -> str:
    """Normalize ASP category labels for persisted document payloads."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "dna",
        "somatic": "dna",
        "rna": "rna",
    }
    return mapping.get(raw, raw or "dna")


def _validated_doc(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalize payload using collection Pydantic contract."""
    try:
        return normalize_collection_document(collection, payload)
    except Exception as exc:
        raise api_error(400, f"Invalid {collection} payload: {exc}") from exc
