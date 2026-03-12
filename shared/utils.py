"""Neutral shared utilities."""

from __future__ import annotations

from typing import Iterable, TypeVar

T = TypeVar("T")


def compact(items: Iterable[T | None]) -> list[T]:
    """Return the non-null items from an iterable.

    Args:
        items: Iterable containing values or ``None`` placeholders.

    Returns:
        A list containing only the non-null values from ``items`` while
        preserving the original order.
    """
    return [item for item in items if item is not None]
