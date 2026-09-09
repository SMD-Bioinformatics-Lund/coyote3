"""Canonical paths for application-owned and center-owned configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path

API_CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_CONFIG_DIR.parents[1]
EMAIL_LOGO_PATH = REPO_ROOT / "api" / "app" / "templates" / "logo.png"
CENTER_CONFIG_DIR = API_CONFIG_DIR / "center"

# Container filesystem contract. Compose mounts the center-owned host data root
# at /data for every API and Celery container; runtime code never receives host
# filesystem paths.
DATA_CONTAINER_ROOT = Path("/data")


def environment_storage_root(environment: str, root: Path = DATA_CONTAINER_ROOT) -> Path:
    """Resolve the environment's application storage directory.

    Args:
        environment: ENV_NAME label; long and short deployment names are accepted.
        root: Mounted application storage root, defaulting to /data.

    Returns:
        Environment directory beneath root.

    Raises:
        ValueError: If the label cannot safely identify a directory.
    """
    name = environment.strip().lower()
    name = {"development": "dev", "production": "prod", "testing": "test", "staging": "stage"}.get(
        name, name
    )
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise ValueError("ENV_NAME must contain only letters, digits, underscores or hyphens")
    return root / f"coyote3_{name}"


COYOTE3_DATA_CONTAINER_ROOT = environment_storage_root(os.getenv("ENV_NAME") or "production")
REPORTS_BASE_PATH = COYOTE3_DATA_CONTAINER_ROOT / "reports"
INGEST_STAGING_DIR = COYOTE3_DATA_CONTAINER_ROOT / "ingest_staging"
INGEST_WATCH_DIR = COYOTE3_DATA_CONTAINER_ROOT / "copied_sample_files" / "yaml"


def initialize_storage_directories() -> None:
    """Create report and ingest working directories with the process user's permissions."""
    for directory in (REPORTS_BASE_PATH, INGEST_STAGING_DIR, INGEST_WATCH_DIR):
        directory.mkdir(parents=True, exist_ok=True)


CONTACT_CONFIG_PATH = CENTER_CONFIG_DIR / "contact.toml"
CLINICAL_VOCABULARY_PATH = CENTER_CONFIG_DIR / "clinical_vocabulary.toml"
CLINICAL_QUERY_POLICY_PATH = CENTER_CONFIG_DIR / "clinical_query_policy.toml"
COLLECTIONS_CONFIG_PATH = CENTER_CONFIG_DIR / "collections.toml"
FILTER_FLAG_METADATA_PATH = CENTER_CONFIG_DIR / "filter_flag_metadata.yaml"
