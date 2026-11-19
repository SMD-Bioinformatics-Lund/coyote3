# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Atomic recovery lifecycle against a synthetic in-memory identity store."""

from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from coyote.contracts.auth import PasswordRecoveryRecord
from coyote_mongo.repositories.users import UsersRepository
from mongo_test_support.settings import audit_context, mongo_runtime
from mongo_test_support.writes import repository_writes  # noqa: F401

pytestmark = pytest.mark.usefixtures("repository_writes")


def test_pending_deduplication_completion_retry_and_provider_change():
    collection = mongomock.MongoClient().synthetic.users
    collection.insert_one(
        {"username": "person", "auth_type": ["ldap"], "is_active": True, "password": "unchanged"}
    )
    repository = UsersRepository(
        SimpleNamespace(
            users_collection=collection,
            app=SimpleNamespace(
                audit=audit_context(), config={}, logger=SimpleNamespace(debug=lambda *a, **k: None)
            ),
        )
    )
    first = PasswordRecoveryRecord(
        request_id="one",
        username="person",
        provider="ldap",
        requested_at=datetime.now(timezone.utc),
    ).model_dump()
    assert repository.request_recovery("person", first)["request_id"] == "one"
    assert (
        repository.request_recovery("person", {**first, "request_id": "duplicate"})["request_id"]
        == "one"
    )
    assert len(repository.recovery_requests()) == 1
    completed = repository.complete_recovery("one", "first-admin")
    assert PasswordRecoveryRecord.model_validate(completed).status == "completed"
    assert repository.complete_recovery("one", "second-admin") == completed
    assert repository.recovery_requests() == []
    assert collection.find_one({"username": "person"})["password"] == "unchanged"
    repository.request_recovery("person", {**first, "request_id": "two"})
    collection.update_one({"username": "person"}, {"$set": {"auth_type": ["local"]}})
    assert repository.complete_recovery("two", "admin") is None
    collection.update_one({"username": "person"}, {"$set": {"is_active": False}})
    assert repository.request_recovery("person", first) is None


def test_recovery_notification_retries_preserve_read_state_and_are_dismissible():
    from coyote.application.notifications.service import NotificationService
    from coyote_mongo.repositories.notifications import NotificationsRepository

    collection = mongomock.MongoClient().synthetic.notifications
    repository = NotificationsRepository(
        SimpleNamespace(app=mongo_runtime(), notifications_collection=collection)
    )
    service = NotificationService(
        notification_repository=repository, user_repository=SimpleNamespace(), retention_days=30
    )
    data = dict(
        audience="users",
        recipients=["admin"],
        email_recipients=["admin"],
        tone="warning",
        category="security",
        title="Recovery",
        message="Verify identity",
        source="Account recovery",
        created_by="system",
        event_id="password-recovery:r1:requested",
    )
    identity = service.create_notification(**data)
    assert repository.mark_read(identity, "admin") is True
    assert service.create_notification(**data) == identity
    assert collection.count_documents({}) == 1
    assert repository.get_notification(identity)["read_by"] == ["admin"]
    assert repository.dismiss(identity, "admin") is True
    assert repository.mark_read(identity, "other-user") is False
