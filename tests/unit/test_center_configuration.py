"""Regression coverage for the center configuration directory contract."""

import yaml

from api.config.loaders.collections import load_collection_mapping
from api.config.loaders.contact import load_contact_config
from api.config.paths import (
    ASSAY_CATALOG_PATH,
    CENTER_CONFIG_DIR,
    CLINICAL_VOCABULARY_PATH,
    COLLECTIONS_CONFIG_PATH,
    CONTACT_CONFIG_PATH,
    FILTER_FLAG_METADATA_PATH,
)


def test_center_owned_assets_reside_in_one_directory():
    """All deployer-editable assets live below the canonical center directory."""
    expected = (
        CONTACT_CONFIG_PATH,
        CLINICAL_VOCABULARY_PATH,
        COLLECTIONS_CONFIG_PATH,
        ASSAY_CATALOG_PATH,
        FILTER_FLAG_METADATA_PATH,
    )
    assert all(path.parent == CENTER_CONFIG_DIR and path.is_file() for path in expected)


def test_center_contact_and_collection_configuration_loads():
    """The committed center configuration has the minimum deployable content."""
    contact = load_contact_config(
        CONTACT_CONFIG_PATH,
        organization_name="Test center",
        public_base_url="https://example.test",
        script_name="/coyote3",
    )
    collections = load_collection_mapping(
        primary_database="arbitrary_center_database",
        knowledgebase_database="arbitrary_knowledgebase_database",
        bam_database="arbitrary_bam_database",
    )

    assert contact["organization"]["name"] == "Test center"
    assert contact["contacts"]
    assert collections["arbitrary_center_database"]["samples_collection"] == "samples"
    assert (
        collections["arbitrary_knowledgebase_database"]["civic_variants_collection"]
        == "civic_variants"
    )
    assert "civic_variants_collection" not in collections["arbitrary_center_database"]
    assert collections["arbitrary_bam_database"]["bam_samples"] == "samples"


def test_assay_catalog_machine_identifiers_use_underscores():
    """Catalog ids are safe to bind directly to ASP, ASPC, and rule-release scopes."""
    payload = yaml.safe_load(ASSAY_CATALOG_PATH.read_text(encoding="utf-8")) or {}

    def strings(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {"catalog_id", "asp_id", "key"} and isinstance(nested, str):
                    yield nested
                yield from strings(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from strings(nested)

    invalid = sorted(value for value in strings(payload) if "-" in value)
    assert not invalid, f"Catalog machine identifiers must use underscores: {invalid}"
