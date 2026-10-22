"""Audit hashes survive BSON round trips and expose alteration and truncation."""

from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories import audit_integrity


@pytest.fixture
def collection(monkeypatch):
    """Exercise database semantics in memory; real transaction races have integration coverage."""
    monkeypatch.setattr(
        audit_integrity, "run_transaction", lambda client, operation: operation(None)
    )
    return mongomock.MongoClient().identity.audit_events


def event():
    """Return an event with sub-millisecond timestamp precision to test BSON normalization."""
    return {
        "_id": ObjectId(),
        "occurred_at": datetime.now(timezone.utc),
        "retention_class": "traceability",
        "source": {"environment": "test"},
        "message": "Synthetic clinical change",
    }


def test_append_is_idempotent_and_checkpoint_detects_suffix_deletion(collection):
    first, second = event(), event()
    audit_integrity.append_event(collection, first)
    audit_integrity.append_event(collection, {**first, "message": "Must not replace"})
    audit_integrity.append_event(collection, second)
    result = audit_integrity.verify_chain(collection)
    assert result["valid"] and result["chains"][0]["sequence"] == 2
    assert collection.count_documents({}) == 2
    assert collection.find_one({"_id": first["_id"]})["message"] == first["message"]
    collection.delete_one({"_id": second["_id"]})
    assert not audit_integrity.verify_chain(collection, checkpoint=result)["valid"]


@pytest.mark.parametrize("mutation", ["content", "sequence", "expiry", "head", "all"])
def test_tampering_is_detected(collection, mutation):
    document = event()
    audit_integrity.append_event(collection, document)
    checkpoint = audit_integrity.verify_chain(collection)
    if mutation == "content":
        collection.update_one({}, {"$set": {"message": "Altered"}})
    elif mutation == "sequence":
        collection.update_one({}, {"$set": {"integrity.sequence": 8}})
    elif mutation == "expiry":
        collection.update_one({}, {"$set": {"expires_at": datetime.now(timezone.utc)}})
    elif mutation == "head":
        collection.database.audit_chain_heads.delete_many({})
    else:
        collection.delete_many({})
        collection.database.audit_chain_heads.delete_many({})
    assert not audit_integrity.verify_chain(collection, checkpoint=checkpoint)["valid"]


def test_legacy_and_operational_events_are_explicitly_outside_the_chain(collection):
    collection.insert_one(event())
    operational = {**event(), "retention_class": "operational"}
    audit_integrity.append_event(collection, operational)
    result = audit_integrity.verify_chain(collection)
    assert result["valid"]
    assert result["unchained_legacy_events"] == 1
    assert not result["chains"]
    assert "integrity" not in collection.find_one({"_id": operational["_id"]})


@pytest.mark.parametrize(
    "checkpoint",
    [
        {},
        {"valid": False, "chains": []},
        {"valid": True, "chains": [None]},
        {"valid": True, "chains": [{"chain_id": "a", "sequence": True, "entry_hash": "0" * 64}]},
    ],
)
def test_untrusted_or_malformed_checkpoint_is_rejected(collection, checkpoint):
    """A failed or malformed prior verification cannot become a trusted anchor."""
    with pytest.raises(ValueError, match="Checkpoint"):
        audit_integrity.verify_chain(collection, checkpoint=checkpoint)
