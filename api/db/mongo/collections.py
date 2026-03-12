"""Collection names and adapter access helpers."""

from __future__ import annotations

from collections.abc import Mapping


def configured_collections(config: Mapping[str, object], db_name: str) -> dict[str, str]:
    collections = config.get("DB_COLLECTIONS_CONFIG", {})
    if not isinstance(collections, Mapping):
        return {}
    db_config = collections.get(db_name, {})
    return dict(db_config) if isinstance(db_config, Mapping) else {}
