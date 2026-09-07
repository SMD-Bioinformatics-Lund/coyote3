"""Shared helpers for table search, sorting, and pagination preparation."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Any, Callable, Iterable, Mapping, Sequence

SortSpec = tuple[str, str]


def numeric_value(value: Any) -> float | None:
    """Convert values to sortable numbers when possible."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sortable_text(value: Any) -> str | None:
    """Normalize strings for stable case-insensitive sorting."""
    if value in (None, ""):
        return None
    return str(value).lower()


def parse_sort_specs(query_params: Mapping[str, Any]) -> list[SortSpec]:
    """Parse multi-column table sorting from query parameters.

    The canonical format is ``sort=field:asc,other:desc``.
    """
    raw_sort = str(query_params.get("sort", "") or "").strip()
    specs: list[SortSpec] = []
    if raw_sort:
        for part in raw_sort.split(","):
            field, _, direction = part.partition(":")
            field = field.strip()
            direction = direction.strip().lower()
            if not field:
                continue
            specs.append((field, "desc" if direction == "desc" else "asc"))
    return specs


def sort_spec_to_query_value(specs: Sequence[SortSpec]) -> str:
    """Serialize parsed sort specs for response metadata."""
    return ",".join(f"{field}:{direction}" for field, direction in specs)


def sort_items(
    items: Sequence[dict[str, Any]],
    *,
    specs: Sequence[SortSpec],
    value_getter: Callable[[dict[str, Any], str], Any],
) -> list[dict[str, Any]]:
    """Sort all filtered table rows with per-column directions."""
    if not specs:
        return list(items)

    def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        for field, direction in specs:
            left_value = value_getter(left, field)
            right_value = value_getter(right, field)
            left_missing = left_value is None
            right_missing = right_value is None
            if left_missing and right_missing:
                continue
            if left_missing:
                return 1
            if right_missing:
                return -1
            if left_value == right_value:
                continue
            result = -1 if left_value < right_value else 1
            return -result if direction == "desc" else result
        return 0

    return sorted(items, key=cmp_to_key(compare))


def search_items(
    items: Iterable[dict[str, Any]],
    *,
    search_query: str,
    text_builder: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    """Filter rows by normalized text from a table-specific builder."""
    terms = [term for term in search_query.lower().split() if term]
    if not terms:
        return list(items)
    return [item for item in items if all(term in text_builder(item).lower() for term in terms)]
