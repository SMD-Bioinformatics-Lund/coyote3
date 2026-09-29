"""Crash recovery and rollback of transaction-owned audit receipts."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import AutoReconnect, OperationFailure

from api.infra.mongo.repositories.audit_outbox import (
    AuditOutboxRepository,
    enqueue_audit,
    insert_audited,
    update_audited,
)
from api.infra.mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from api.infra.mongo.transactions import run_transaction
from tests.unit.reporting.test_clinical_rules import _document


@pytest.fixture
def databases(monkeypatch):
    uri = os.getenv("AUDIT_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set AUDIT_TEST_MONGO_URI for disposable audit outbox tests")
    with (
        MongoClient(uri, serverSelectionTimeoutMS=3000) as owner,
        MongoClient(
            os.getenv("AUDIT_TEST_DEST_URI") or uri, serverSelectionTimeoutMS=3000
        ) as destination,
    ):
        source_db = owner[f"coyote3_outbox_test_{uuid4().hex}"]
        target_db = destination[f"coyote3_outbox_test_{uuid4().hex}"]
        monkeypatch.setenv("ENV_NAME", "test")
        monkeypatch.setenv("IDENTITY_MONGO_URI", os.getenv("AUDIT_TEST_DEST_URI") or uri)
        monkeypatch.setenv("IDENTITY_DB", target_db.name)
        try:
            yield source_db, target_db
        finally:
            owner.drop_database(source_db.name)
            destination.drop_database(target_db.name)


def commit_change(database, *, fail=False):
    def change(session):
        database.business.insert_one({"_id": "synthetic"}, session=session)
        enqueue_audit(
            database,
            session,
            event_type="synthetic.created",
            resource_type="synthetic",
            resource_id="synthetic",
            actor="operator",
            metadata={"token": "must-not-persist"},
        )
        if fail:
            raise RuntimeError("Synthetic abort")

    run_transaction(database.client, change)


def test_abort_leaves_neither_business_change_nor_success_audit(databases):
    source, _ = databases
    with pytest.raises(RuntimeError, match="Synthetic abort"):
        commit_change(source, fail=True)
    assert source.business.count_documents({}) == 0
    assert source.audit_outbox.count_documents({}) == 0


def test_configuration_receipts_are_only_written_for_committed_changes(databases):
    source, _ = databases
    collection = source.configuration
    insert_audited(collection, {"_id": "synthetic", "is_active": True})
    assert source.audit_outbox.count_documents({}) == 1
    assert (
        update_audited(collection, {"_id": "missing"}, {"$set": {"is_active": False}}).matched_count
        == 0
    )
    assert source.audit_outbox.count_documents({}) == 1
    assert (
        update_audited(
            collection, {"_id": "synthetic"}, {"$set": {"is_active": False}}
        ).modified_count
        == 1
    )
    assert source.audit_outbox.count_documents({}) == 2
    assert (
        update_audited(
            collection, {"_id": "synthetic"}, {"$set": {"is_active": False}}
        ).modified_count
        == 0
    )
    assert source.audit_outbox.count_documents({}) == 2


def test_committed_change_survives_until_separate_client_delivers(databases):
    source, target = databases
    commit_change(source)
    pending = source.audit_outbox.find_one()
    assert pending["event"]["actor"]["username"] == "operator"
    assert pending["event"]["metadata"]["token"] == "[redacted]"
    assert source.business.count_documents({}) == 1
    assert target.audit_events.count_documents({}) == 0
    assert AuditOutboxRepository(source).deliver(target.audit_events, environment="test") == 1
    assert source.audit_outbox.count_documents({}) == 0
    stored = target.audit_events.find_one()
    assert stored["_id"] == pending["_id"]
    assert stored["source"]["environment"] == "test"
    assert "expires_at" not in stored


def test_crash_after_delivery_does_not_duplicate_or_overwrite(databases, monkeypatch):
    source, target = databases
    commit_change(source)
    original_delete = Collection.delete_one

    def crash(collection, *args, **kwargs):
        if collection.name == "audit_outbox":
            raise RuntimeError("Synthetic crash after acknowledgement")
        return original_delete(collection, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Collection, "delete_one", crash)
        with pytest.raises(RuntimeError, match="Synthetic crash"):
            AuditOutboxRepository(source).deliver(target.audit_events, environment="test")
    first = target.audit_events.find_one()
    assert source.audit_outbox.count_documents({}) == 1
    assert AuditOutboxRepository(source).deliver(target.audit_events, environment="test") == 1
    assert target.audit_events.count_documents({}) == 1
    assert target.audit_events.find_one() == first


def test_outbox_rejects_sessions_from_another_client(databases):
    source, target = databases
    with target.client.start_session() as session, session.start_transaction():
        with pytest.raises(ValueError, match="owning database"):
            enqueue_audit(
                source, session, event_type="synthetic", resource_type="test", resource_id="one"
            )


def test_worker_cannot_consume_another_environment_or_destination(databases, monkeypatch):
    source, target = databases
    commit_change(source)
    repository = AuditOutboxRepository(source)
    assert repository.deliver(target.audit_events, environment="production") == 0
    monkeypatch.setenv("IDENTITY_DB", "another_center")
    assert repository.deliver(target.audit_events, environment="test") == 0
    assert source.audit_outbox.count_documents({}) == 1
    assert target.audit_events.count_documents({}) == 0


def test_destination_outage_keeps_committed_receipt(databases, monkeypatch):
    source, target = databases
    commit_change(source)
    original_update = Collection.update_one

    def fail(collection, *args, **kwargs):
        if collection.database.name == target.name:
            raise AutoReconnect("Synthetic identity outage")
        return original_update(collection, *args, **kwargs)

    monkeypatch.setattr(Collection, "update_one", fail)
    with pytest.raises(AutoReconnect):
        AuditOutboxRepository(source).deliver(target.audit_events, environment="test")
    assert source.business.count_documents({}) == 1
    assert source.audit_outbox.count_documents({}) == 1


def test_transaction_retry_does_not_keep_aborted_attempt_receipt(databases):
    source, _ = databases
    attempts = 0

    def change(session):
        nonlocal attempts
        attempts += 1
        source.business.insert_one({"_id": "synthetic"}, session=session)
        enqueue_audit(
            source,
            session,
            event_type="synthetic.created",
            resource_type="test",
            resource_id="synthetic",
        )
        if attempts == 1:
            raise OperationFailure(
                "Synthetic write conflict",
                code=112,
                details={"errorLabels": ["TransientTransactionError"]},
            )

    run_transaction(source.client, change)
    assert attempts == 2
    assert source.business.count_documents({}) == 1
    assert source.audit_outbox.count_documents({}) == 1


def test_clinical_rule_insert_rolls_back_when_outbox_write_fails(databases, monkeypatch):
    source, _ = databases
    repository = ClinicalRuleSetRepository(
        SimpleNamespace(
            client=source.client,
            clinical_rule_sets_collection=source.rules,
            clinical_rule_revisions_collection=source.revisions,
        )
    )
    original_insert = Collection.insert_one

    def fail_outbox(collection, *args, **kwargs):
        if collection.name == "audit_outbox":
            raise RuntimeError("Synthetic outbox failure")
        return original_insert(collection, *args, **kwargs)

    document = _document().model_dump(mode="python", by_alias=True)
    with monkeypatch.context() as scoped:
        scoped.setattr(Collection, "insert_one", fail_outbox)
        with pytest.raises(RuntimeError, match="Synthetic outbox failure"):
            repository.insert(document, action="draft_created", actor="author")
    assert source.rules.count_documents({}) == 0
    assert source.revisions.count_documents({}) == 0
    assert source.audit_outbox.count_documents({}) == 0
    repository.insert(document, action="draft_created", actor="author")
    assert source.audit_outbox.count_documents({}) == 1
    assert source.audit_outbox.find_one()["event"]["metadata"]["revision_hash"]
