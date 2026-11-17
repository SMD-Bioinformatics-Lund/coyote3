"""Core-only synthetic capabilities; no host configuration or persistence imports."""

import hashlib
import json
from pathlib import Path

import pytest
from coyote.contracts.resource_integrity import using_resource_hasher


@pytest.fixture(autouse=True)
def synthetic_resource_hasher():
    """Bind a deterministic test codec without selecting a database implementation."""

    def digest(content):
        return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()

    with using_resource_hasher(digest):
        yield


def pytest_collection_modifyitems(items):
    """Mark only this package's tests, including its fast smoke subset."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            item.add_marker(pytest.mark.unit)
            if "smoke" in path.relative_to(directory).parts:
                item.add_marker(pytest.mark.smoke)


@pytest.fixture
def manifest_payload() -> dict:
    """Return a single-case DNA manifest without host-specific configuration."""
    return {
        "name": "SYNTHETIC-CASE",
        "asp_id": "example-assay",
        "environment": "development",
        "asp_family": "panel-dna",
        "asp_category": "dna",
        "case_id": "SYNTHETIC-CASE",
        "sample_no": 1,
        "pipeline": "example-pipeline",
        "vcf_files": "variants.vcf.gz",
    }
