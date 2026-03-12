"""Neutral shared utilities."""

from __future__ import annotations

from typing import Iterable, TypeVar

T = TypeVar("T")


def compact(items: Iterable[T | None]) -> list[T]:
    """Return the non-null items from an iterable."""
    return [item for item in items if item is not None]
