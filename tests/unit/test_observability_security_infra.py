"""Tests for CLL-style observability and security infrastructure."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from api.infra.security.sessions import MongoApiSessionRepository
from api.application.audit.service import AuditService
from api.infra.observability.logging import (
    JsonFormatter,
    RequestContext,
    bind_request_context,
    reset_request_context,
)
from api.security.tokens import token_hash


class _InsertResult:
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
    service = AuditService(collection, retention_days=90, environment="test")

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
    assert event_id == stored["_id"]
    assert stored["metadata"] == {"password": "[redacted]", "safe": 1}
    assert stored["actor"]["username"] == "alice"
    assert stored["expires_at"] > datetime.now(timezone.utc) + timedelta(days=89)


def test_json_formatter_includes_bound_request_context():
    formatter = JsonFormatter()
    token = bind_request_context(
        RequestContext(
            request_id="rid-1",
            client_ip="127.0.0.1",
            method="POST",
            path="/api/v1/samples",
        )
    )
    try:
        record = logging.LogRecord(
            "coyote3.test",
            logging.INFO,
            __file__,
            1,
            "hello",
            (),
            None,
        )
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_context(token)

    assert payload["request_id"] == "rid-1"
    assert payload["client_ip"] == "127.0.0.1"
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/v1/samples"

