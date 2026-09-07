"""Common result types for internal workflows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReplaceDocumentResult(BaseModel):
    """Summarize a replace-one persistence operation."""

    model_config = ConfigDict(frozen=True)

    matched_count: int
    modified_count: int
    upserted_id: str | None = None
