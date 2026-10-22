"""Shared helpers for table search, sorting, and pagination preparation."""

from __future__ import annotations

from functools import cmp_to_key
from heapq import nsmallest
from typing import Any, Callable, Iterable, Mapping, Sequence

from api.infra.external_sort import SORT_CHUNK_ROWS, sorted_page

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

    return sorted(items, key=table_sort_key(specs=specs, value_getter=value_getter))


def table_sort_key(
    *,
    specs: Sequence[SortSpec],
    value_getter: Callable[[dict[str, Any], str], Any],
) -> Callable[[dict[str, Any]], Any]:
    """Build a comparator key preserving missing-last and mixed-direction ordering."""

    def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        """Compare rows using the enclosing sort specifications and value getter.

        Args:
            left: First table row.
            right: Second table row.

        Returns:
            Negative, zero, or positive ordering, with None values last in either direction.

        Raises:
            TypeError: Nonmissing values returned by the getter cannot be ordered.
        """
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

    return cmp_to_key(compare)


def select_table_rows(
    items: Iterable[dict[str, Any]],
    *,
    search_query: str,
    text_builder: Callable[[dict[str, Any]], str],
    specs: Sequence[SortSpec],
    value_getter: Callable[[dict[str, Any], str], Any],
    page: int | None,
    per_page: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search streamed rows and select a page with bounded sorting memory.

    Args:
        items: Single-pass, already clinically filtered and enriched finding stream.
        search_query: Whitespace-separated terms, all required case-insensitively.
        text_builder: Existing table-specific searchable text projection.
        specs: Stable multi-column order; no specs preserves source order.
        value_getter: Existing table-specific sort projection, with missing values last.
        page: Positive page number, or None for a complete export.
        per_page: Validated page size from request_pagination.

    Returns:
        Selected rows and unchanged table pagination metadata. Unsorted pages retain
        only their rows; deep sorted pages use a private temporary spool. Full exports
        retain their complete output. Every match is counted.
    """
    terms = search_query.lower().split()
    total = 0

    def matches() -> Iterable[dict[str, Any]]:
        """Count matching rows while yielding them once to the page selector."""
        nonlocal total
        for item in items:
            if terms:
                text = text_builder(item).lower()
                if not all(term in text for term in terms):
                    continue
            total += 1
            yield item

    start = ((page or 1) - 1) * per_page
    end = start + per_page
    if page is None:
        selected = sort_items(list(matches()), specs=specs, value_getter=value_getter)
    elif specs:
        key = table_sort_key(specs=specs, value_getter=value_getter)
        if end > SORT_CHUNK_ROWS:
            selected = sorted_page(matches(), key=key, start=start, end=end)
        else:
            selected = nsmallest(end, matches(), key=key)[start:end]
    else:
        selected = [row for index, row in enumerate(matches()) if start <= index < end]
    return selected, {
        "total": total,
        "count": total,
        "page_count": len(selected),
        "page": page or 1,
        "per_page": per_page if page is not None else (total or 50),
        "has_previous": page is not None and page > 1,
        "has_next": page is not None and end < total,
    }


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
