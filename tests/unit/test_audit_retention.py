"""Retained clinical history, operational replay, and cleanup boundaries."""

from datetime import datetime, timedelta, timezone

import mongomock
from bson import ObjectId

from api.infra.mongo.repositories import audit_integrity
from api.infra.mongo.repositories.app_controls import MongoAppControlsRepository
from api.infra.mongo.repositories.audit import AuditRepository


def test_operational_replay_uses_insert_without_changing_existing_content():
    collection = mongomock.MongoClient().identity.operational_audit_events
    event = {"_id": ObjectId(), "message": "Original"}
    audit_integrity.append_event(collection, event)
    audit_integrity.append_event(collection, {**event, "message": "Replacement"})
    assert collection.count_documents({}) == 1
    assert collection.find_one()["message"] == "Original"


def test_recent_events_include_both_collections_and_cleanup_never_touches_retained_history(
    monkeypatch,
):
    monkeypatch.setattr(
        audit_integrity, "run_transaction", lambda client, operation: operation(None)
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.app_controls.run_transaction",
        lambda client, operation: operation(None),
    )
    client = mongomock.MongoClient(tz_aware=True)
    retained = client.identity.audit_events
    operational = client.identity.operational_audit_events
    repository = AuditRepository(retained, operational_collection=operational)
    old = datetime.now(timezone.utc) - timedelta(days=100)
    repository.persist(
        {
            "_id": ObjectId(),
            "retention_class": "traceability",
            "occurred_at": old,
            "source": {"environment": "test"},
            "message": "Retained",
        }
    )
    repository.persist(
        {
            "_id": ObjectId(),
            "retention_class": "operational",
            "occurred_at": old,
            "message": "Expiring",
        }
    )
    # Pre-upgrade operational events stay readable in their original collection.
    retained.insert_one(
        {
            "_id": ObjectId(),
            "retention_class": "operational",
            "occurred_at": old,
            "message": "Legacy operational",
        }
    )
    assert repository.recent_events(limit=10)["total"] == 3
    controls = MongoAppControlsRepository(client.app, identity_db=client.identity, config={})
    assert controls.delete_operational_audit_before(datetime.now(timezone.utc)) == 1
    assert retained.count_documents({}) == 2
    assert repository.recent_events(limit=10)["total"] == 2
