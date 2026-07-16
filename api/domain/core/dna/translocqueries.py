"""Service-level DNA translocation query builders."""

from __future__ import annotations

from typing import Any


def build_transloc_query(sample_id: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build translocation query for a sample."""
    settings = settings or {}
    return {"SAMPLE_ID": sample_id}
