"""Small Mongo repository helpers with no app-layer dependencies."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import md5
from typing import Any

from api.domain.core.dna.variant_identity import build_simple_id, normalize_simple_id


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def get_simple_id(variant: dict[str, Any]) -> str:
    """Return the canonical simple variant identifier."""
    existing = variant.get("simple_id")
    if existing:
        return normalize_simple_id(existing)
    return build_simple_id(
        variant.get("CHROM"),
        variant.get("POS"),
        variant.get("REF"),
        variant.get("ALT"),
    )


def generate_sample_cache_key(**kwargs: Any) -> str:
    """Generate a stable cache key for sample query parameters."""
    kwargs.pop("self", None)
    kwargs.pop("use_cache", None)
    if "user_groups" in kwargs and isinstance(kwargs["user_groups"], list):
        kwargs["user_groups"] = sorted(kwargs["user_groups"])
    for key, value in kwargs.items():
        if isinstance(value, datetime):
            kwargs[key] = value.date().isoformat()
        elif not isinstance(value, (str, int, float, bool, type(None), list, dict)):
            kwargs[key] = str(value)
    raw_key = json.dumps(kwargs, sort_keys=True, separators=(",", ":"))
    return f"samples:{md5(raw_key.encode()).hexdigest()}"
