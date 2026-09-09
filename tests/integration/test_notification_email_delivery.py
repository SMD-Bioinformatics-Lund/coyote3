"""Exercise MongoDB email leases in an explicitly configured disposable database."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pymongo import MongoClient

from api.application.notifications.service import NotificationService
from api.contracts.notifications import NotificationBroadcastRequest
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.notifications import NotificationsRepository
from scripts.migrate_notification_retention import migrate


@pytest.fixture
def delivery():
    """Create an isolated temporary database; never use deployment notification records."""
    uri = os.getenv("NOTIFICATION_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set NOTIFICATION_TEST_MONGO_URI for disposable email-lease tests")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    database_name = "coyote3_notification_test_" + uuid4().hex
    collection = client[database_name].notifications
    repo = NotificationsRepository(SimpleNamespace(notifications_collection=collection))
    users = {
        "recipient": {
            "username": "recipient",
            "email": "recipient@example.test",
            "is_active": True,
        },
        "other": {"username": "other", "email": "other@example.test", "is_active": True},
    }
    sender = Mock(return_value=True)
    service = NotificationService(
        notification_repository=repo,
        user_repository=SimpleNamespace(
            list_active_users_for_notifications=lambda **kwargs: list(users.values()),
            user_with_id=lambda username: users.get(username),
        ),
        retention_days=30,
        email_sender=sender,
        inbox_url="https://coyote3.example.test/testing/notifications",
    )
    try:
        yield service, repo, collection, users, sender
    finally:
        client.drop_database(database_name)
        client.close()


def publish(service):
    """Create a synthetic private broadcast for one known account."""
    return service.broadcast(
        payload={
            "audience": "selected",
            "recipients": ["recipient"],
            "title": "Private message",
            "message": "Content must remain in the application",
        },
        actor=SimpleNamespace(username="operator"),
    )


def test_broadcast_persists_outbox_before_sending(delivery):
    service, repo, collection, users, sender = delivery
    result = publish(service)
    assert result["email_state"] == "pending"
    sender.assert_not_called()
    assert service.deliver_emails()["sent"] == 1
    assert service.deliver_emails()["sent"] == 0
    sender.assert_called_once()
    message = sender.call_args.kwargs
    assert message["to_email"] == "recipient@example.test"
    assert service.inbox_url in message["text_body"]
    assert "Content must remain" not in message["text_body"]
    assert "Private message" not in message["subject"]
    assert collection.find_one()["email_deliveries"][0]["state"] == "sent"


@pytest.mark.parametrize("reason", ["inactive", "missing", "no_address", "smtp_failure"])
def test_delivery_rechecks_recipient_and_records_failure(delivery, reason):
    service, repo, collection, users, sender = delivery
    publish(service)
    if reason == "inactive":
        users["recipient"]["is_active"] = False
    elif reason == "missing":
        del users["recipient"]
    elif reason == "no_address":
        users["recipient"]["email"] = ""
    else:
        sender.return_value = False
    expected = "failed" if reason == "smtp_failure" else "skipped"
    assert service.deliver_emails()[expected] == 1
    assert collection.find_one()["email_deliveries"][0]["state"] == expected
    service.deliver_emails()
    assert sender.call_count == (1 if reason == "smtp_failure" else 0)


def test_no_smtp_does_not_accumulate_old_messages(delivery):
    service, repo, collection, users, sender = delivery
    service.email_sender = None
    assert publish(service)["email_state"] == "not_configured"
    assert collection.find_one()["email_deliveries"] == []
    assert service.deliver_emails()["status"] == "not_configured"


def test_lease_ownership_and_abandoned_delivery_limit(delivery):
    service, repo, collection, users, sender = delivery
    publish(service)
    row, claim = repo.claim_email()
    assert repo.claim_email() is None
    repo.finish_email(row["_id"], "not-owner", state="sent")
    assert collection.find_one()["email_deliveries"][0]["state"] == "sending"
    collection.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "email_deliveries.0.lease_until": datetime.now(timezone.utc) - timedelta(seconds=1),
                "email_deliveries.0.attempts": 3,
            }
        },
    )
    assert service.deliver_emails()["unknown"] == 1
    sender.assert_not_called()
    assert repo.claim_email() is None


def test_all_audience_is_a_snapshot_not_future_accounts(delivery):
    service, repo, collection, users, sender = delivery
    service.broadcast(
        payload={"audience": "all", "title": "Notice", "message": "Synthetic"},
        actor=SimpleNamespace(username="operator"),
    )
    users["future"] = {"username": "future", "is_active": True}
    assert service.inbox(username="future")["notifications"] == []
    assert service.deliver_emails()["sent"] == 2


def test_read_does_not_dismiss_notification(delivery):
    service, repo, collection, users, sender = delivery
    result = publish(service)
    service.mark_read(notification_id=result["notification_id"], username="recipient")
    inbox = service.inbox(username="recipient")
    assert len(inbox["notifications"]) == 1
    assert inbox["notifications"][0]["read"] is True
    assert inbox["unread_count"] == 0
    with pytest.raises(AppError):
        service.dismiss(notification_id=result["notification_id"], username="recipient")
    assert service.dismiss_all(username="recipient")["changed"] == 0
    assert service.inbox(username="recipient")["notifications"]
    service.dismiss(notification_id=result["notification_id"], username="operator")
    assert service.inbox(username="recipient")["notifications"] == []
    assert collection.count_documents({}) == 1


def test_expiry_hides_broadcast_without_deletion_or_email(delivery):
    service, repo, collection, users, sender = delivery
    publish(service)
    collection.update_one(
        {}, {"$set": {"expires_on": datetime.now(timezone.utc) - timedelta(seconds=1)}}
    )
    assert service.inbox(username="recipient")["notifications"] == []
    assert service.deliver_emails()["sent"] == 0
    assert len(service.sent(username="operator")["notifications"]) == 1
    assert service.sent(username="other")["notifications"] == []
    assert collection.count_documents({}) == 1


def test_withdrawal_stops_queued_email_and_is_idempotent(delivery):
    service, repo, collection, users, sender = delivery
    result = publish(service)
    assert (
        service.dismiss(notification_id=result["notification_id"], username="operator")["changed"]
        == 1
    )
    assert (
        service.dismiss(notification_id=result["notification_id"], username="operator")["changed"]
        == 0
    )
    assert repo.claim_email() is None
    assert collection.count_documents({}) == 1


@pytest.mark.parametrize("expiry", ["2020-01-01T12:00:00Z", "2099-01-01T12:00:00"])
def test_broadcast_rejects_past_and_timezone_naive_expiry(expiry):
    with pytest.raises(ValidationError):
        NotificationBroadcastRequest(
            audience="all", title="Notice", message="Synthetic", expires_at=expiry
        )


def test_retention_migration_is_idempotent_and_preserves_records(delivery):
    service, repo, collection, users, sender = delivery
    publish(service)
    collection.update_one({}, {"$unset": {"is_broadcast": ""}})
    collection.create_index("expires_on", name="expires_on_1", expireAfterSeconds=0)
    assert migrate(collection) == {"ttl_indexes": 1, "broadcasts": 1}
    assert "expireAfterSeconds" in collection.index_information()["expires_on_1"]
    migrate(collection, apply=True)
    assert migrate(collection) == {"ttl_indexes": 0, "broadcasts": 0}
    assert collection.count_documents({}) == 1
    assert "expireAfterSeconds" not in collection.index_information()["expires_on_1"]
    with pytest.raises(AppError):
        service.dismiss(notification_id=str(collection.find_one()["_id"]), username="recipient")
