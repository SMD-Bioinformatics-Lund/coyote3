"""Password reset atomicity and session revocation regressions using synthetic accounts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest

from api.infra.mongo.repositories.users import UsersRepository
from api.infra.security.sessions import MongoApiSessionRepository


def test_reset_token_can_replace_password_only_once():
    collection = mongomock.MongoClient().test.users
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
    repository = UsersRepository(SimpleNamespace(users_collection=collection))

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


@pytest.mark.parametrize("previous", [None, datetime(2025, 1, 1, tzinfo=timezone.utc)])
def test_password_change_revokes_sessions_and_allows_fresh_login(previous):
    collection = mongomock.MongoClient().test.sessions
    user = SimpleNamespace(username="synthetic", password_updated_on=previous)
    repository = MongoApiSessionRepository(collection, user_loader=lambda _: user, ttl_seconds=60)
    session = repository.create(user)
    assert repository.get(session.token) is not None
    user.password_updated_on = datetime.now(timezone.utc)
    assert repository.get(session.token) is None
    fresh = repository.create(user)
    assert repository.get(fresh.token) is not None
