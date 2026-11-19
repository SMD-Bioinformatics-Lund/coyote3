"""Fake driver writes for worker orchestration tests; durability uses real MongoDB tests."""

import pytest
from coyote_mongo.repositories import base
from pymongo.collection import Collection


@pytest.fixture
def repository_writes(monkeypatch):
    """Keep synthetic queue/permission tests independent of transaction transport."""

    def write(collection, operation, *args, context, **options):
        if isinstance(collection, Collection):
            raise AssertionError("Worker query doubles must not access a real database")
        return getattr(collection, operation)(*args, **options)

    monkeypatch.setattr(base, "write_with_audit", write)
