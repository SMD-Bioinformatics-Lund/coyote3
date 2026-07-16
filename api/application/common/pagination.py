"""Shared application-layer pagination helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def request_pagination(request: Any, *, default: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    """Read bounded pagination parameters from a FastAPI request."""
    params = getattr(request, "query_params", {}) or {}
    page = _positive_int(params.get("page"), 1)
    per_page = _positive_int(params.get("per_page"), default)
    return page, min(per_page, MAX_PAGE_SIZE)


def paginate_items(
    items: Sequence[Any], *, page: int, per_page: int
) -> tuple[list[Any], dict[str, Any]]:
    """Return a page slice and normalized metadata for an in-memory result set."""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = list(items[start:end])
    return page_items, {
        "total": total,
        "count": total,
        "page_count": len(page_items),
        "page": page,
        "per_page": per_page,
        "has_previous": page > 1,
        "has_next": end < total,
    }


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
