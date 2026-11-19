"""Data and audit receipts are inseparable on an owned disposable MongoDB replica."""

import pytest
from coyote_mongo.repositories.mutations import write_with_audit
from coyote_mongo.transactions import run_transaction
from pymongo.errors import OperationFailure

from tests.fixtures.mongo_settings import audit_context
from tests.integration.test_ingest_job_recovery import database as _database

database = _database


def test_mutations_retain_receipts_without_copying_values(database):
    db, _, _ = database
    context = audit_context()
    created = write_with_audit(
        db.records,
        "insert_one",
        {"name": "synthetic-private", "password": "synthetic-secret"},
        context=context,
    )
    write_with_audit(
        db.records,
        "update_one",
        {"_id": created.inserted_id},
        {"$set": {"name": "synthetic-updated"}},
        context=context,
    )
    write_with_audit(db.records, "delete_one", {"_id": created.inserted_id}, context=context)
    receipts = list(db.audit_outbox.find())
    assert db.records.count_documents({}) == 0
    assert [row["event"]["metadata"]["operation"] for row in receipts] == [
        "insert_one",
        "update_one",
        "delete_one",
    ]
    assert all(row["event"]["resource"]["id"] == str(created.inserted_id) for row in receipts)
    assert "synthetic-private" not in str(receipts)
    assert "synthetic-secret" not in str(receipts)
    assert "synthetic-updated" not in str(receipts)


@pytest.mark.parametrize("outer_transaction", [False, True])
def test_unwritable_audit_aborts_data_even_when_caller_catches_failure(database, outer_transaction):
    db, _, _ = database
    db.create_collection("audit_outbox", validator={"must_never_exist": {"$exists": True}})
    context = audit_context()
    if outer_transaction:
        with db.client.start_session() as session:
            session.start_transaction()
            db.records.insert_one({"_id": "earlier-write"}, session=session)
            with pytest.raises(OperationFailure):
                write_with_audit(
                    db.records, "insert_one", {"_id": "rejected"}, context=context, session=session
                )
            assert not session.in_transaction
    else:
        with pytest.raises(OperationFailure):
            write_with_audit(db.records, "insert_one", {"_id": "rejected"}, context=context)
    assert db.records.count_documents({}) == 0
    assert db.audit_outbox.count_documents({}) == 0


def test_owning_transaction_rolls_back_all_receipts_and_records(database):
    db, _, _ = database

    def change(session):
        write_with_audit(
            db.samples, "insert_one", {"_id": "sample"}, context=audit_context(), session=session
        )
        write_with_audit(
            db.findings,
            "insert_many",
            [{"_id": "finding", "SAMPLE_ID": "sample"}],
            context=audit_context(),
            session=session,
        )
        raise ValueError("synthetic downstream validation failure")

    with pytest.raises(ValueError, match="downstream"):
        run_transaction(db.client, change)
    assert db.samples.count_documents({}) == 0
    assert db.findings.count_documents({}) == 0
    assert db.audit_outbox.count_documents({}) == 0


def test_credential_keys_and_values_never_enter_audit(database):
    db, _, _ = database
    write_with_audit(
        db.sessions,
        "insert_one",
        {"_id": "synthetic-token-hash", "csrf_token": "synthetic-csrf"},
        context=audit_context(),
        record_ids=False,
    )
    receipt = db.audit_outbox.find_one()
    assert receipt is not None
    assert "synthetic-token-hash" not in str(receipt)
    assert "synthetic-csrf" not in str(receipt)


def test_sorted_claim_receipt_names_the_claimed_record(database):
    from pymongo import ReturnDocument

    db, _, _ = database
    db.jobs.insert_many([{"_id": "later", "priority": 2}, {"_id": "first", "priority": 1}])
    row = write_with_audit(
        db.jobs,
        "find_one_and_update",
        {},
        {"$set": {"claimed": True}},
        sort=[("priority", 1)],
        return_document=ReturnDocument.AFTER,
        context=audit_context(),
    )
    assert row["_id"] == "first"
    assert db.audit_outbox.find_one()["event"]["resource"]["id"] == "first"


def test_repository_password_change_rolls_back_when_audit_is_rejected(database):
    from types import SimpleNamespace

    from coyote_mongo.repositories.users import UsersRepository

    from tests.fixtures.mongo_settings import mongo_runtime

    db, _, _ = database
    db.users.insert_one({"username": "synthetic", "password": "original-hash"})
    repository = UsersRepository(SimpleNamespace(app=mongo_runtime(), users_collection=db.users))
    db.create_collection("audit_outbox", validator={"must_never_exist": {"$exists": True}})
    with pytest.raises(OperationFailure):
        repository.update_password("synthetic", "replacement-hash")
    assert db.users.find_one()["password"] == "original-hash"


def test_session_is_not_issued_without_its_audit_receipt(database):
    from types import SimpleNamespace

    from coyote_mongo.sessions import MongoApiSessionRepository

    db, _, _ = database
    user = SimpleNamespace(username="synthetic")
    repository = MongoApiSessionRepository(
        db.sessions, user_loader=lambda _: user, ttl_seconds=60, context=audit_context()
    )
    db.create_collection("audit_outbox", validator={"must_never_exist": {"$exists": True}})
    with pytest.raises(OperationFailure):
        repository.create(user)
    assert db.sessions.count_documents({}) == 0


def test_mutation_receipt_reaches_retained_audit_exactly_once(database):
    from coyote_mongo.repositories.audit_outbox import AuditOutboxRepository

    db, _, _ = database
    context = audit_context()
    write_with_audit(db.records, "insert_one", {"_id": "synthetic"}, context=context)
    outbox = AuditOutboxRepository(db)
    assert (
        outbox.deliver(db.audit_events, environment=context.environment, route=context.route) == 1
    )
    assert (
        outbox.deliver(db.audit_events, environment=context.environment, route=context.route) == 0
    )
    assert db.audit_events.count_documents({"event_type": "database.insert_one"}) == 1
    event = db.audit_events.find_one()
    assert event["retention_class"] == "traceability"
    assert event["immutable"] is True


def test_namespace_maintenance_records_intent_and_failed_outcome(database):
    from coyote_mongo.repositories.maintenance_audit import audit_maintenance

    db, _, _ = database
    with pytest.raises(ValueError, match="synthetic"):
        with audit_maintenance(db, context=audit_context(), operation="rename", resource="records"):
            raise ValueError("synthetic private error detail")
    events = [row["event"] for row in db.audit_outbox.find().sort("_id", 1)]
    assert [row["outcome"] for row in events] == ["pending", "failure"]
    assert events[0]["resource"]["id"] == events[1]["resource"]["id"]
    assert events[1]["metadata"]["error_type"] == "ValueError"
    assert "private error detail" not in str(events)


def test_ingest_replacement_uses_same_transaction_as_its_receipt(database):
    from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway

    db, _, _ = database
    db.records.insert_one({"_id": "synthetic", "value": "before"})
    gateway = IngestCollectionGateway(context=audit_context(), collections={"records": db.records})
    result = run_transaction(
        db.client,
        lambda session: gateway.replace_document(
            "records",
            {"_id": "synthetic"},
            {"_id": "synthetic", "value": "after"},
            upsert=False,
            session=session,
        ),
    )
    assert result.modified_count == 1
    assert db.records.find_one()["value"] == "after"
    assert db.audit_outbox.find_one()["event"]["event_type"] == "database.replace_one"
