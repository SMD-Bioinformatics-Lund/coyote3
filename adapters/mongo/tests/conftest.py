"""Adapter-only synthetic capabilities, without API configuration discovery."""

from pathlib import Path

import pytest
from coyote.contracts.resource_integrity import using_resource_hasher
from coyote_mongo.resource_integrity import resource_content_hash


@pytest.fixture(autouse=True)
def persistence_codec():
    """Use the adapter's actual codec for repository contract tests."""
    with using_resource_hasher(resource_content_hash):
        yield


def pytest_collection_modifyitems(items):
    """Select adapter-owned unit and smoke tests independently of other projects."""
    directory = Path(__file__).parent
    for item in items:
        path = Path(item.path)
        if path.is_relative_to(directory):
            parts = path.relative_to(directory).parts
            item.add_marker(pytest.mark.integration if "integration" in parts else pytest.mark.unit)
            if "smoke" in parts:
                item.add_marker(pytest.mark.smoke)
