"""Verify runtime repository wiring covers every supported dependent ingest type."""

from types import SimpleNamespace

import mongomock
from coyote.contracts.schemas.registry import INGEST_DEPENDENT_COLLECTIONS
from coyote_mongo.config.collections import load_collection_mapping
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from coyote_mongo.runtime_adapter import MongoAdapter
from mongo_test_support.settings import audit_context


def test_runtime_gateway_covers_all_dependent_analysis_collections():
    adapter = MongoAdapter()
    adapter.app = SimpleNamespace(
        audit=audit_context(), config={"DB_COLLECTIONS_CONFIG": load_collection_mapping()}
    )
    client = mongomock.MongoClient()
    for attribute in ("coyote_db", "identity_db", "knowledgebase_db", "bam_db"):
        setattr(adapter, attribute, client[attribute])
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    gateway = IngestCollectionGateway.from_store(adapter)
    assert set(INGEST_DEPENDENT_COLLECTIONS.values()) <= gateway.collection_names()
    assert gateway.collection("pgx") is adapter.pgx_repository.get_collection()
