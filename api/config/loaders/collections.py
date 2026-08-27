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
    """Load logical mappings and bind them to the configured database names."""
    path_obj = Path(config_path)
    if not path_obj.exists():
        raise RuntimeError(f"Collections configuration does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)

    logical_sections = {"primary": primary_database, "bam": bam_database}
    missing = [section for section in logical_sections if section not in raw]
    if missing:
        raise ValueError(
            f"Logical section(s) {', '.join(missing)} are missing from collections "
            f"configuration: {path_obj}"
        )
    return {
        database: {str(key): str(value) for key, value in dict(raw[section]).items()}
        for section, database in logical_sections.items()
    }
