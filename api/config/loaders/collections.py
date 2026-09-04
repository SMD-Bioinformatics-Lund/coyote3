"""Load the center-owned MongoDB collection mapping."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from api.config.paths import COLLECTIONS_CONFIG_PATH


def load_collection_section(
    section: str,
    *,
    config_path: str | Path = COLLECTIONS_CONFIG_PATH,
) -> dict[str, str]:
    """Load one logical collection section for a maintenance command."""
    path_obj = Path(config_path)
    if not path_obj.exists():
        raise RuntimeError(f"Collections configuration does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)
    mapping = raw.get(section)
    if not isinstance(mapping, dict):
        raise ValueError(f"Logical section '{section}' is missing from {path_obj}")
    return {str(key): str(value) for key, value in mapping.items()}


def load_collection_mapping(
    *,
    primary_database: str,
    identity_database: str,
    knowledgebase_database: str,
    bam_database: str,
    config_path: str | Path = COLLECTIONS_CONFIG_PATH,
) -> dict[str, dict[str, str]]:
    """Bind primary, identity, knowledgebase, and BAM mappings to database names."""
    logical_sections = {
        "primary": primary_database,
        "identity": identity_database,
        "knowledgebase": knowledgebase_database,
        "bam": bam_database,
    }
    return {
        database: load_collection_section(section, config_path=config_path)
        for section, database in logical_sections.items()
    }
