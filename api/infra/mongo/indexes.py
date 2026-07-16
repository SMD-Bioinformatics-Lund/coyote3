"""Mongo index bootstrap helpers."""

from __future__ import annotations


def ensure_adapter_indexes(adapter) -> None:
    """Ensure repository-backed indexes exist.

    The historical ``MongoAdapter`` creates indexes while binding repositories, so this
    helper simply exists as the single API-owned entrypoint for that behavior.
    """
    if hasattr(adapter, "_setup_repositories"):
        adapter._setup_repositories()
