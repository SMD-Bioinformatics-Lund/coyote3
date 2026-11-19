"""Explicit persistence codec used by synthetic API composition tests."""

import pytest
from coyote.contracts.resource_integrity import using_resource_hasher
from coyote_mongo.resource_integrity import resource_content_hash


@pytest.fixture(autouse=True)
def persistence_codec():
    """Bind the deployed codec only for composed API tests."""
    with using_resource_hasher(resource_content_hash):
        yield
