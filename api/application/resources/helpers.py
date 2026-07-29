"""Common helpers and constants for admin resource services."""

from __future__ import annotations

from typing import Any

from api.config.constants import normalize_asp_category
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error


def _normalize_asp_category(value: Any) -> str:
    """Normalize ASP category labels to managed DNA/RNA categories."""
    return normalize_asp_category(value or "dna").upper()


def _normalize_asp_category_doc(value: Any) -> str:
    """Normalize ASP category labels for persisted document payloads."""
    return normalize_asp_category(value or "dna")


def _validated_doc(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalize payload using collection Pydantic contract."""
    try:
        return normalize_collection_document(collection, payload)
    except Exception as exc:
        raise api_error(400, f"Invalid {collection} payload: {exc}") from exc
