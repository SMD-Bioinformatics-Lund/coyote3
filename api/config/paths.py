"""Canonical paths for application-owned and center-owned configuration."""

from __future__ import annotations

from pathlib import Path

API_CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_CONFIG_DIR.parents[1]
CENTER_CONFIG_DIR = API_CONFIG_DIR / "center"
CLINICAL_REPORTING_RULES_DIR = REPO_ROOT / "clinical_reporting_rules"

# Container filesystem contract. Compose mounts the center-owned host data root
# at /data for every API and Celery container; runtime code never receives host
# filesystem paths.
DATA_CONTAINER_ROOT = Path("/data")
COYOTE3_DATA_CONTAINER_ROOT = DATA_CONTAINER_ROOT / "coyote3"
REPORTS_BASE_PATH = COYOTE3_DATA_CONTAINER_ROOT / "reports"
INGEST_STAGING_DIR = COYOTE3_DATA_CONTAINER_ROOT / "ingest_staging"
INGEST_WATCH_DIR = COYOTE3_DATA_CONTAINER_ROOT / "copied_sample_files" / "yaml"

CONTACT_CONFIG_PATH = CENTER_CONFIG_DIR / "contact.toml"
CLINICAL_VOCABULARY_PATH = CENTER_CONFIG_DIR / "clinical_vocabulary.toml"
CLINICAL_QUERY_POLICY_PATH = CENTER_CONFIG_DIR / "clinical_query_policy.toml"
COLLECTIONS_CONFIG_PATH = CENTER_CONFIG_DIR / "collections.toml"
ASSAY_CATALOG_PATH = CENTER_CONFIG_DIR / "assay_catalog.yaml"
FILTER_FLAG_METADATA_PATH = CENTER_CONFIG_DIR / "filter_flag_metadata.yaml"
