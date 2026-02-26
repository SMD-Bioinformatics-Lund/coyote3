"""Common payload models used by Flask common blueprint routes."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiCommonGeneInfoPayload(ApiModel):
    gene: JsonDict = Field(default_factory=dict)


class ApiCommonTieredVariantPayload(ApiModel):
    variant: JsonDict = Field(default_factory=dict)
    docs: list[JsonDict] = Field(default_factory=list)
    tier: int | None = None
    error: str | None = None


class ApiCommonTieredVariantSearchPayload(ApiModel):
    docs: list[JsonDict] = Field(default_factory=list)
    search_str: str | None = None
    search_mode: str | None = None
    include_annotation_text: bool = False
    tier_stats: JsonDict = Field(default_factory=dict)
    assays: list[str] | None = None
    assay_choices: list[Any] = Field(default_factory=list)

