"""In-memory ingest doubles preserving ordinary parsing and collection operations."""

import pytest
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway


def audit_context():
    """Return an explicit synthetic audit identity with no deployment configuration."""
    return AuditContext(environment="test", route="synthetic-demo-test")


class MemoryGateway(IngestCollectionGateway):
    """Use real collection operations without claiming to emulate transactional rollback."""

    def run_transaction(self, operation):
        """Execute one operation against isolated in-memory test collections."""
        return operation(None)


class MemoryVault:
    """Preserve insert-once transcript documents in an in-memory annotation collection."""

    def __init__(self, collection):
        """Bind the synthetic annotation collection."""
        self.collection = collection

    def upsert_many(self, documents, *, session=None):
        """Retain the first transcript document for each variant and annotation version."""
        for document in documents:
            key = {field: document[field] for field in ("simple_id_hash", "vep_version")}
            self.collection.update_one(key, {"$setOnInsert": document}, upsert=True)


@pytest.fixture
def ingest_writes(monkeypatch):
    """Use fake collection writes while checking parsing and demo protection rules.

    Disposable integration/browser tests cover transaction and audit durability.
    """
    from coyote_mongo import persistence
    from coyote_mongo.repositories import ingest_gateway
    from pymongo.collection import Collection

    def write(collection, operation, *args, context, **options):
        if isinstance(collection, Collection):
            raise AssertionError("Demo query doubles must not access a real database")
        return getattr(collection, operation)(*args, **options)

    monkeypatch.setattr(persistence, "write_with_audit", write)
    monkeypatch.setattr(ingest_gateway, "write_with_audit", write)
