"""Common helpers and constants for admin resource services."""

from __future__ import annotations

import re
from typing import Any

from api.config.constants import normalize_asp_category
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error


def require_new_identifier(value: object, *, label: str) -> str:
    """Require lowercase words separated by single underscores for a new identity.

    Args:
        value: Proposed business identifier, not a reference to an existing record.
        label: Contract field name included in the validation response.

    Returns:
        The unchanged identifier when it meets the creation policy.

    Raises:
        AppError: With status 422 for blanks, uppercase, whitespace, hyphens,
            non-ASCII characters or leading, trailing or repeated underscores.

    Notes:
        Call only when registering an identity, never when reading or revising
        an existing one. This function does not translate or alias identifiers.
    """
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", value):
        raise api_error(
            422,
            f"Invalid {label}",
            details=f"{label} must use lowercase letters and digits with single underscores between words.",
            category="validation",
        )
    return value


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
