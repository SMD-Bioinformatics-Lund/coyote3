"""Shared value normalizers for collection document contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_ampersand_terms(value: Any) -> list[str]:
    """Normalize one or many ampersand-delimited terms into a stable list."""
    if value is None or value == "":
        return []
    values: Iterable[Any]
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable) and not isinstance(value, dict):
        values = value
    else:
        values = [value]

    terms: list[str] = []
    seen: set[str] = set()
    for item in values:
        for raw_term in str(item or "").split("&"):
            term = raw_term.strip()
            if term and term not in seen:
                seen.add(term)
                terms.append(term)
    return terms
