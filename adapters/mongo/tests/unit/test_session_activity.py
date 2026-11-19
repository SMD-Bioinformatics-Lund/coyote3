"""Session counts follow login validity rather than MongoDB TTL cleanup."""

# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest
from coyote.application.accounts.tokens import token_hash
from coyote_mongo.sessions import MongoApiSessionRepository
from mongo_test_support.settings import audit_context
from mongo_test_support.writes import repository_writes  # noqa: F401

pytestmark = pytest.mark.usefixtures("repository_writes")


@pytest.fixture
def sessions():
    accounts = {
        name: SimpleNamespace(username=name, credential_version="current")
        for name in ("active", "idle", "disabled", "deleted", "changed")
    }
    collection = mongomock.MongoClient().synthetic.session_activity
    repository = MongoApiSessionRepository(
        collection, user_loader=accounts.get, ttl_seconds=3600, context=audit_context()
    )
    return repository, accounts, collection


def test_activity_counts_unique_valid_users_and_excludes_stale_credentials(sessions):
    repository, accounts, collection = sessions
    first = repository.create(accounts["active"])
    repository.create(accounts["active"])
    idle = repository.create(accounts["idle"])
    repository.create(accounts["disabled"])
    repository.create(accounts["deleted"])
    repository.create(accounts["changed"])
    accounts["disabled"] = None
    del accounts["deleted"]
    accounts["changed"].credential_version = "replacement"
    collection.update_one(
        {"_id": token_hash(idle.token)},
        {"$set": {"last_seen_at": datetime.now(timezone.utc) - timedelta(minutes=10)}},
    )
    before = list(collection.find())

    summary = repository.activity_summary(recent_activity_seconds=300)

    assert (summary.signed_in_users, summary.active_sessions, summary.recently_active_users) == (
        2,
        3,
        1,
    )
    assert summary.observed_at.tzinfo is not None
    assert list(collection.find()) == before, "Reading counts must not refresh or delete sessions"
    assert first.token not in summary.model_dump_json()
    assert first.csrf_token not in summary.model_dump_json()
    assert "active" not in summary.model_dump().values()


def test_logout_expiry_and_account_changes_reduce_counts_without_ttl_cleanup(sessions):
    repository, accounts, collection = sessions
    logged_out = repository.create(accounts["active"])
    expired = repository.create(accounts["idle"])
    repository.delete(logged_out.token)
    collection.update_one(
        {"_id": token_hash(expired.token)},
        {"$set": {"expires_at": datetime.now(timezone.utc)}},
    )
    summary = repository.activity_summary(recent_activity_seconds=300)
    assert summary.signed_in_users == summary.active_sessions == summary.recently_active_users == 0
    assert collection.count_documents({}) == 1, "Expired documents need not have been deleted"

    repository.create(accounts["active"])
    assert repository.activity_summary(recent_activity_seconds=300).signed_in_users == 1
    accounts["active"].credential_version = "rotated"
    assert repository.activity_summary(recent_activity_seconds=300).signed_in_users == 0


def test_missing_and_future_activity_do_not_claim_recent_presence(sessions):
    repository, accounts, collection = sessions
    missing = repository.create(accounts["active"])
    future = repository.create(accounts["idle"])
    collection.update_one({"_id": token_hash(missing.token)}, {"$unset": {"last_seen_at": ""}})
    collection.update_one(
        {"_id": token_hash(future.token)},
        {"$set": {"last_seen_at": datetime.now(timezone.utc) + timedelta(days=1)}},
    )
    summary = repository.activity_summary(recent_activity_seconds=300)
    assert summary.signed_in_users == 2
    assert summary.recently_active_users == 0
