"""Tests for CLL-style observability and security infrastructure."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from coyote.application.accounts.tokens import token_hash
from coyote.application.audit.service import AuditService
from coyote_mongo.repositories.audit import AuditRepository
from coyote_mongo.sessions import MongoApiSessionRepository


class _InsertResult:
    acknowledged = True

    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _UpdateResult:
    matched_count = 1


class _Collection:
    name = "test"

    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        stored = dict(doc)
        stored.setdefault("_id", f"id-{len(self.docs) + 1}")
        self.docs.append(stored)
        return _InsertResult(stored["_id"])

    def find_one(self, query):
        for doc in self.docs:
            if "_id" in query and doc.get("_id") != query["_id"]:
                continue
            expires_query = query.get("expires_at")
            if isinstance(expires_query, dict) and "$gt" in expires_query:
                if doc.get("expires_at") <= expires_query["$gt"]:
                    continue
            return doc
        return None

    def update_one(self, *_args, **_kwargs):
        return _UpdateResult()

    def delete_one(self, query):
        self.docs = [doc for doc in self.docs if doc.get("_id") != query.get("_id")]


def test_mongo_session_repository_stores_only_token_hash():
    user = SimpleNamespace(username="alice")
    collection = _Collection()
    repo = MongoApiSessionRepository(collection, user_loader=lambda _username: user, ttl_seconds=60)

    session = repo.create(user)

    assert collection.docs[0]["_id"] == token_hash(session.token)
    assert session.token not in json.dumps(collection.docs[0], default=str)
    assert repo.get(session.token).user is user
    repo.delete(session.token)
    assert collection.docs == []


def test_audit_service_redacts_sensitive_metadata_and_sets_expiry():
    collection = _Collection()
    service = AuditService(
        AuditRepository(collection, operational_collection=collection),
        retention_days=90,
        environment="test",
    )

    event_id = service.record(
        "auth.login.failed",
        "Rejected",
        severity="warning",
        category="security",
        outcome="failure",
        actor="alice",
        metadata={"password": "secret", "safe": 1},
    )

    stored = collection.docs[0]
    assert event_id == str(stored["_id"])
    assert stored["metadata"] == {"password": "[redacted]", "safe": 1}
    assert stored["actor"]["username"] == "alice"
    assert stored["retention_class"] == "operational"
    assert stored["immutable"] is False
    assert stored["expires_at"] > datetime.now(timezone.utc) + timedelta(days=89)


def test_traceability_audit_events_do_not_expire(monkeypatch):
    import mongomock
    from coyote_mongo.repositories import audit_integrity

    monkeypatch.setattr(
        audit_integrity, "run_transaction", lambda client, operation: operation(None)
    )
    collection = mongomock.MongoClient().identity.audit_events
    service = AuditService(
        AuditRepository(
            collection, operational_collection=collection.database.operational_audit_events
        ),
        retention_days=90,
        environment="test",
    )

    service.record(
        "clinical.configuration.updated",
        "Updated ASP hema_gmsv1",
        category="clinical_configuration",
        actor="admin",
        resource_type="asp",
        resource_id="hema_gmsv1",
        retention_class="traceability",
    )

    stored = collection.find_one()
    assert stored["retention_class"] == "traceability"
    assert stored["immutable"] is True
    assert "expires_at" not in stored
