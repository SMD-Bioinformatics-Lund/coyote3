"""Initial sample attribution is server-owned and recovered only from creation evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.ingest.collection_writes import upsert_collection_document
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.settings import audit_context
from mongo_test_support.writes import repository_writes  # noqa: F401

pytestmark = pytest.mark.usefixtures("repository_writes")


@pytest.mark.parametrize("existing", [None, {}, {"ingested_by": "first", "ingest_source": "api"}])
def test_sample_replacement_preserves_initial_attribution(monkeypatch, existing):
    collection = Mock()
    collection.find_one.return_value = existing
    collection.replace_one.return_value = SimpleNamespace(
        matched_count=1, modified_count=1, upserted_id=None
    )
    monkeypatch.setattr(
        "coyote.application.ingest.collection_writes.normalize_collection_document",
        lambda name, document: document,
    )
    upsert_collection_document(
        SimpleNamespace(
            collection_gateway=IngestCollectionGateway(
                context=audit_context(), collections={"samples": collection}
            )
        ),
        collection="samples",
        match={"name": "synthetic"},
        document={"ingested_by": "forged"},
        ingested_by="operator",
        upsert=True,
    )
    written = collection.replace_one.call_args.args[1]
    assert written["ingested_by"] == (
        "operator" if existing is None else existing.get("ingested_by")
    )
    assert written["ingest_source"] == (
        "collection_import" if existing is None else existing.get("ingest_source")
    )
