"""Regression coverage for the center configuration directory contract."""

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
        primary_database="coyote3_dev",
        bam_database="BAM_Service",
    )

    assert contact["organization"]["name"] == "Test center"
    assert contact["contacts"]
    assert collections["coyote3_dev"]["samples_collection"] == "samples"
