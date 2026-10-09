"""Committed event delivery, group scoping, and independent inbox state."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect

from api.application.notifications.activity import ActivityNotificationService
from api.application.notifications.service import NotificationService
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.notification_activity import NotificationActivityRepository
from api.infra.mongo.repositories.notifications import NotificationsRepository


def fixture():
    client = mongomock.MongoClient()
    repo = NotificationsRepository(
        SimpleNamespace(notifications_collection=client.app.notifications)
    )
    users = Mock()
    users.list_active_users_for_notifications.return_value = [
        {
            "username": "group.reader",
            "asp_groups": ["hematology"],
            "asp_ids": ["panel"],
            "envs": ["production"],
        },
        {
            "username": "other.group",
            "asp_groups": ["solid"],
            "asp_ids": ["panel"],
            "envs": ["production"],
        },
        {
            "username": "wrong.assay",
            "asp_groups": ["hematology"],
            "asp_ids": ["another"],
            "envs": ["production"],
        },
        {
            "username": "wrong.environment",
            "asp_groups": ["hematology"],
            "asp_ids": ["panel"],
            "envs": ["testing"],
        },
    ]
    notifications = NotificationService(
        notification_repository=repo, user_repository=users, retention_days=180
    )
    samples = Mock()
    samples.get_notification_sample.return_value = {
        "name": "DEMO",
        "asp_group": "hematology",
        "asp_id": "panel",
        "environment": "production",
    }
    activity = NotificationActivityRepository(
        audit_collection=client.identity.audit,
        versions_collection=client.kb.versions,
        notifications=client.app.notifications,
    )
    service = ActivityNotificationService(
        activity_repository=activity,
        notifications=notifications,
        users=users,
        samples=samples,
        environment="production",
    )
    return client, service, notifications, repo


def event(kind="api.mutation.succeeded", resource="genelist", **extra):
    return {
        "_id": ObjectId(),
        "occurred_at": datetime.now(timezone.utc),
        "source": {"environment": "production"},
        "event_type": kind,
        "outcome": "success",
        "resource": {"type": resource, "id": "demo"},
        **extra,
    }


def test_shared_events_reach_every_user_and_replay_preserves_read_state():
    client, delivery, inbox, repo = fixture()
    source = event(metadata={"action": "created"})
    client.identity.audit.insert_one(source)
    assert delivery.deliver() == 1
    for username in ("group.reader", "other.group", "new.user"):
        assert len(inbox.inbox(username=username)["notifications"]) == 1
    repo.mark_read(str(source["_id"]), "group.reader")
    repo.create({**client.app.notifications.find_one(), "read_by": []})
    assert delivery.deliver() == 0
    assert inbox.inbox(username="group.reader")["notifications"][0]["read"]
    assert not inbox.inbox(username="other.group")["notifications"][0]["read"]


def test_inbox_pagination_keeps_read_messages_and_has_no_duplicate_pages():
    client, _, _, repo = fixture()
    now = datetime.now(timezone.utc)
    client.app.notifications.insert_many(
        [{"audience": "all", "created_on": now, "read_by": ["reader"]} for _ in range(205)]
    )
    first = repo.list_for_user("reader", limit=200)
    second = repo.list_for_user("reader", limit=200, offset=200)
    assert len(first) == 200
    assert len(second) == 5
    assert len({row["_id"] for row in first + second}) == 205


def test_report_audience_is_restricted_to_sample_group_and_scope():
    client, delivery, inbox, _ = fixture()
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "sample", "report_num": 2})
    )
    delivery.deliver()
    assert inbox.inbox(username="group.reader")["notifications"][0]["title"] == "Sample reported"
    for username in ("other.group", "wrong.assay", "wrong.environment"):
        assert inbox.inbox(username=username)["notifications"] == []


def test_failures_and_unrelated_private_events_are_not_broadcast():
    client, delivery, _, _ = fixture()
    client.identity.audit.insert_many(
        [
            event(outcome="failure"),
            event(resource="sample"),
            event("auth.password.changed", "user"),
            event(source={"environment": "development"}),
        ]
    )
    assert delivery.deliver() == 0


def test_late_audit_and_successful_knowledgebase_publication_are_delivered_once():
    client, delivery, _, _ = fixture()
    now = datetime.now(timezone.utc)
    client.kb.versions.insert_many(
        [
            {
                "_id": "demo:1",
                "source": "demo",
                "release": "1",
                "status": "active",
                "published_at": now,
            },
            {"_id": "failed:1", "status": "failed", "published_at": now},
        ]
    )
    assert delivery.deliver() == 1
    client.identity.audit.insert_one(event(occurred_at=now - timedelta(days=1)))
    assert delivery.deliver() == 1
    assert delivery.deliver() == 0
    assert client.app.notifications.count_documents({}) == 2


def test_mark_unread_is_idempotent_and_recipient_scoped():
    client, delivery, inbox, repo = fixture()
    doc = event("report.saved", "report", metadata={"sample_oid": "sample"})
    client.identity.audit.insert_one(doc)
    delivery.deliver()
    identity = str(doc["_id"])
    repo.mark_read(identity, "group.reader")
    for _ in range(2):
        assert inbox.mark_unread(notification_id=identity, username="group.reader")["changed"] == 1
    assert not inbox.inbox(username="group.reader")["notifications"][0]["read"]
    with pytest.raises(AppError):
        inbox.mark_unread(notification_id=identity, username="other.group")


def test_missing_sample_never_broadcasts_report_identity():
    client, delivery, inbox, _ = fixture()
    delivery.samples.get_notification_sample.return_value = None
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "deleted"})
    )
    assert delivery.deliver() == 1
    assert inbox.inbox(username="group.reader")["notifications"] == []


def test_sample_lookup_failure_is_retried_without_losing_the_notification():
    client, delivery, _, _ = fixture()
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "sample"})
    )
    delivery.samples.get_notification_sample.side_effect = AutoReconnect("synthetic outage")
    with pytest.raises(AutoReconnect):
        delivery.deliver()
    assert client.app.notifications.count_documents({}) == 0
    delivery.samples.get_notification_sample.side_effect = None
    assert delivery.deliver() == 1
