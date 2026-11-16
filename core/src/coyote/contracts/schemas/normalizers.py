# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Shared value normalizers for collection document contracts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any


def parse_reference_timestamp(value: object) -> datetime:
    """Parse supported CIViC source timestamp encodings in one place.

    Args:
        value: Existing datetime or source text in ISO or timestamp/timezone form.

    Returns:
        Existing datetime or a parsed value, without inventing a missing timezone.

    Raises:
        ValueError: Neither supported source format can parse the value.
    """
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S %Z")


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
