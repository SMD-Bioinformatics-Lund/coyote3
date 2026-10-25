"""Verify runtime repository wiring covers every supported dependent ingest type."""

from types import SimpleNamespace

import mongomock

from api.config.collections import load_collection_mapping
from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.runtime_adapter import MongoAdapter
from coyote3.contracts.schemas.registry import INGEST_DEPENDENT_COLLECTIONS


def test_runtime_gateway_covers_all_dependent_analysis_collections():
    adapter = MongoAdapter()
    adapter.app = SimpleNamespace(config={"DB_COLLECTIONS_CONFIG": load_collection_mapping()})
    client = mongomock.MongoClient()
    for attribute in ("coyote_db", "identity_db", "knowledgebase_db", "bam_db"):
        setattr(adapter, attribute, client[attribute])
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    gateway = IngestCollectionGateway.from_store(adapter)
    assert set(INGEST_DEPENDENT_COLLECTIONS.values()) <= gateway.collection_names()
    assert gateway.collection("pgx") is adapter.pgx_repository.get_collection()
