"""Explicit fake-driver boundary for query and document-shape tests.

These tests exercise selectors, authorization and record updates using MongoMock or
small driver doubles. They do not establish transaction or audit durability; those
properties are exercised against the owned replica set in root integration tests.
"""

from importlib import import_module

import pytest
from pymongo.collection import Collection


@pytest.fixture
def repository_writes(monkeypatch):
    """Forward writes to fake collections without claiming transactional behavior."""

    def write(collection, operation, *args, context=None, record_ids=True, actor=None, **options):
        if isinstance(collection, Collection):
            raise AssertionError("The query-test write fixture must never access a real database")
        return getattr(collection, operation)(*args, **options)

    for name in (
        "repositories.base",
        "repositories.service_tokens",
        "repositories.app_controls",
        "repositories.notification_activity",
        "repositories.report_artifact_erasure",
        "repositories.knowledgebase_publications",
        "sessions",
        "persistence",
    ):
        module = import_module(f"coyote_mongo.{name}")
        monkeypatch.setattr(module, "write_with_audit", write, raising=True)
