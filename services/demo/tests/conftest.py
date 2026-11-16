"""Synthetic package settings and independently owned test markers."""

import os
from pathlib import Path

import pytest

for name, value in {
    "COYOTE4_MONGO_URI": "mongodb://localhost:27017",
    "COYOTE4_DB": "coyote4_test",
    "IDENTITY_DB": "coyote4_identity_test",
    "KNOWLEDGEBASE_DB": "coyote4_knowledgebase_test",
    "BAM_DB": "bam_test",
}.items():
    os.environ.setdefault(name, value)


def pytest_collection_modifyitems(items):
    """Classify package tests without importing host fixtures or external test suites."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            parts = path.relative_to(directory).parts
            item.add_marker(pytest.mark.integration if "integration" in parts else pytest.mark.unit)
            if "smoke" in parts:
                item.add_marker(pytest.mark.smoke)
