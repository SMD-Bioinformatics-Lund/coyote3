"""Mongo index bootstrap helpers."""

from __future__ import annotations


def ensure_adapter_indexes(adapter) -> None:
    """Ensure handler-backed indexes exist.

    The legacy ``MongoAdapter`` creates indexes while binding handlers, so this
    helper simply exists as the single API-owned entrypoint for that behavior.
    """
    if hasattr(adapter, "_setup_handlers"):
        adapter._setup_handlers()
