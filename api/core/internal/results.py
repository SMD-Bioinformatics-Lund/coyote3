"""Shared result types for internal workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplaceDocumentResult:
    """Summarize a replace-one persistence operation."""

    matched_count: int
    modified_count: int
    upserted_id: str | None = None
