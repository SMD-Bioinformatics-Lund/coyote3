"""Load the center-owned MongoDB collection mapping."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from api.config.paths import COLLECTIONS_CONFIG_PATH


def load_collection_mapping(
    *,
    primary_database: str,
    bam_database: str,
    config_path: str | Path = COLLECTIONS_CONFIG_PATH,
) -> dict[str, dict[str, str]]:
    """Load mappings for the configured application and BAM-service databases."""
    path_obj = Path(config_path)
    if not path_obj.exists():
        raise RuntimeError(f"Collections configuration does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)

    required = (primary_database, bam_database)
    missing = [database for database in required if database not in raw]
    if missing:
        raise ValueError(
            f"Database(s) {', '.join(missing)} are missing from collections configuration: {path_obj}"
        )
    return {
        database: {str(key): str(value) for key, value in dict(raw[database]).items()}
        for database in required
    }
