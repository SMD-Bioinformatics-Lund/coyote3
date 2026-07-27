"""Canonical paths for application-owned and center-owned configuration."""

from __future__ import annotations

from pathlib import Path

API_CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_CONFIG_DIR.parents[1]
CENTER_CONFIG_DIR = API_CONFIG_DIR / "center"

CONTACT_CONFIG_PATH = CENTER_CONFIG_DIR / "contact.toml"
CLINICAL_VOCABULARY_PATH = CENTER_CONFIG_DIR / "clinical_vocabulary.toml"
COLLECTIONS_CONFIG_PATH = CENTER_CONFIG_DIR / "collections.toml"
ASSAY_CATALOG_PATH = CENTER_CONFIG_DIR / "assay_catalog.yaml"
FILTER_FLAG_METADATA_PATH = CENTER_CONFIG_DIR / "filter_flag_metadata.yaml"
