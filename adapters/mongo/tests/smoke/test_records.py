"""MongoDB adapters expose portable values rather than provider objects to the core."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from coyote.contracts.operations import OperationResult
from coyote.domain.record_identity import RecordIdentity
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.records import application_record, storage_record
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from coyote_mongo.resource_integrity import resource_content_hash
from coyote_mongo.results import (
    operation_from_delete,
    operation_from_insert_many,
    operation_from_insert_one,
    operation_from_update,
)
from mongo_test_support.writes import repository_writes  # noqa: F401
from pymongo.results import DeleteResult, InsertManyResult, InsertOneResult, UpdateResult

pytestmark = pytest.mark.usefixtures("repository_writes")


def test_driver_write_results_are_projected_at_the_adapter_boundary():
    """Keep counts and identities stable without exporting driver result factories."""
    identity = ObjectId()
    inserted = operation_from_insert_one(InsertOneResult(identity, True))
    assert inserted.inserted_id == str(identity)
    assert inserted.inserted_count == 1
    updated = operation_from_update(
        UpdateResult({"n": 1, "nModified": 0, "upserted": identity}, True)
    )
    assert updated.upserted_id == str(identity)
    assert updated.modified_count == 0
    assert operation_from_delete(DeleteResult({"n": 2}, True)).deleted_count == 2
    assert operation_from_insert_many(InsertManyResult([identity], True)).inserted_count == 1
    assert not hasattr(OperationResult, "from_update")


def test_extended_json_is_decoded_before_application_contract_validation():
    """Decode nested MongoDB wrappers without mutating the incoming source record."""
    identity = str(ObjectId())
    source = {
        "_id": {"$oid": identity},
        "created_on": {"$date": "2026-01-01T00:00:00Z"},
        "history": [{"on": {"$date": {"$numberLong": "0"}}}],
    }
    result = application_record(source)
    assert result["_id"] == identity
    assert result["created_on"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert result["history"][0]["on"] == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert source["_id"] == {"$oid": identity}


def test_portable_resource_records_preserve_existing_mongo_integrity_hashes():
    """Projection cannot invalidate captured assay or gene-list evidence."""
    source = {"_id": ObjectId(), "lists": [{"_id": ObjectId(), "genes": ["TP53"]}]}
    projected = application_record(source)
    assert isinstance(projected["_id"], RecordIdentity)
    assert isinstance(projected["_id"], str)
    assert resource_content_hash(projected) == resource_content_hash(source)
    assert storage_record(projected) == source
    assert isinstance(source["_id"], ObjectId)


def test_ingest_gateway_converts_string_ids_without_exposing_bson_to_the_workflow():
    """Allocate and translate provider identities exclusively inside the adapter."""
    identity = ObjectId()
    recorded = []

    def find_one(selector, *, session):
        """Capture the provider request and emulate its stored sample response."""
        recorded.append(selector)
        return {"_id": identity, "name": "synthetic"}

    def insert_one(document, *, session):
        """Capture the provider record supplied by the adapter."""
        recorded.append(document)

    gateway = IngestCollectionGateway(
        context=AuditContext(environment="test", route="synthetic-records"),
        collections={"samples": SimpleNamespace(find_one=find_one, insert_one=insert_one)},
    )
    selector = {"_id": str(identity)}
    assert gateway.find_document("samples", selector) == {"_id": str(identity), "name": "synthetic"}
    gateway.create_sample({"_id": str(identity), "name": "synthetic"}, session=None)
    assert all(record["_id"] == identity for record in recorded)
    assert selector == {"_id": str(identity)}
