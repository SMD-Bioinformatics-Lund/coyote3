"""Common route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CommonGeneInfoPayload(BaseModel):
    """Represent the common gene info payload.
    """
    gene: dict[str, Any] | None = None


class CommonTieredVariantContextPayload(BaseModel):
    """Represent the common tiered variant context payload.
    """
    variant: dict[str, Any]
    docs: list[dict[str, Any]]
    tier: int
    error: str | None = None


class CommonTieredVariantSearchPayload(BaseModel):
    """Represent the common tiered variant search payload.
    """
    docs: list[dict[str, Any]]
    search_str: str | None = None
    search_mode: str
    include_annotation_text: bool
    tier_stats: dict[str, Any]
    assays: list[str] | None = None
    assay_choices: list[str]
