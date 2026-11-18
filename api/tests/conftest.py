"""Synthetic API host settings and persistence codec for isolated host tests."""

import os
from pathlib import Path

import pytest
from coyote.contracts.resource_integrity import using_resource_hasher
from coyote_mongo.resource_integrity import resource_content_hash

for name, value in {
    "COYOTE4_MONGO_URI": "mongodb://localhost:27017",
    "COYOTE4_DB": "coyote4_test",
    "IDENTITY_DB": "coyote4_identity_test",
    "KNOWLEDGEBASE_DB": "coyote4_knowledgebase_test",
    "BAM_DB": "coyote4_bam_test",
}.items():
    os.environ.setdefault(name, value)


@pytest.fixture(autouse=True)
def persistence_codec():
    """Bind the host's explicit codec only while this test executes."""
    with using_resource_hasher(resource_content_hash):
        yield


def pytest_collection_modifyitems(items):
    """Label API tests without depending on the root suite's bootstrap."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            item.add_marker(pytest.mark.api)
            if "smoke" in path.relative_to(directory).parts:
                item.add_marker(pytest.mark.smoke)
