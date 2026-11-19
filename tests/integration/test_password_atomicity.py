"""Password reset atomicity and session revocation regressions using synthetic accounts on a disposable replica set."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from coyote_mongo.repositories.users import UsersRepository
from coyote_mongo.sessions import MongoApiSessionRepository

from tests.fixtures.mongo_settings import audit_context, mongo_runtime
from tests.integration.test_ingest_job_recovery import database as _database

database = _database


def test_reset_token_can_replace_password_only_once(database):
    db, _, _ = database
    collection = db.users
    collection.insert_one(
        {
            "username": "synthetic",
            "is_active": True,
            "auth_type": ["local"],
            "password": "old",
            "password_action_token_hash": "token",
            "password_action_purpose": "reset",
            "password_action_expires_at": datetime.now(timezone.utc) + timedelta(minutes=1),
        }
    )
    repository = UsersRepository(SimpleNamespace(app=mongo_runtime(), users_collection=collection))

    def consume(index):
        return repository.consume_password_action_token(
            user_id="synthetic", token_hash="token", purpose="reset", password_hash=f"new-{index}"
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(consume, range(8)))
    assert results.count(True) == 1
    document = collection.find_one({"username": "synthetic"})
    assert document["password"] == f"new-{results.index(True)}"
    assert "password_action_token_hash" not in document
    assert document["must_change_password"] is False


@pytest.mark.parametrize("previous", [None, "old-credential-fingerprint"])
def test_password_change_revokes_sessions_and_allows_fresh_login(database, previous):
    db, _, _ = database
    collection = db.sessions
    user = SimpleNamespace(username="synthetic", credential_version=previous)
    repository = MongoApiSessionRepository(
        collection, user_loader=lambda _: user, ttl_seconds=60, context=audit_context()
    )
    session = repository.create(user)
    assert repository.get(session.token) is not None
    user.credential_version = "new-credential-fingerprint"
    assert repository.get(session.token) is None
    fresh = repository.create(user)
    assert repository.get(fresh.token) is not None
