"""Committed event delivery, group scoping, and independent inbox state."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect

from api.infra.mongo.repositories.notification_activity import NotificationActivityRepository
from api.infra.mongo.repositories.notifications import NotificationsRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.security.policy import build_access_policy
from coyote3.application.notifications.access import SampleNotificationAccess
from coyote3.application.notifications.activity import ActivityNotificationService
from coyote3.application.notifications.service import NotificationService
from coyote3.domain.exceptions import AppError
from tests.fixtures.api.permission_catalog import PermissionCatalog


def principal(username, **overrides):
    return SimpleNamespace(
        **{
            "username": username,
            "roles": ["reader"],
            "asp_groups": ["hematology"],
            "asp_ids": ["panel"],
            "envs": ["production"],
            **overrides,
        }
    )


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
    for user in users.list_active_users_for_notifications.return_value:
        user["roles"] = ["reader"]
    samples = Mock()
    samples.get_notification_sample.return_value = {
        "name": "DEMO",
        "asp_group": "hematology",
        "asp_id": "panel",
        "environment": "production",
    }
    roles = Mock()
    roles.get_all_roles.return_value = [{"role_id": "reader", "permissions": ["sample:view"]}]
    access = SampleNotificationAccess(
        samples=samples,
        roles=roles,
        permissions=PermissionCatalog(),
        policy_factory=build_access_policy,
    )
    notifications = NotificationService(
        notification_repository=repo,
        user_repository=users,
        retention_days=180,
        sample_access=access,
    )
    activity = NotificationActivityRepository(
        audit_collection=client.identity.audit,
        operational_collection=client.identity.operational_audit_events,
        versions_collection=client.kb.versions,
        notifications=client.app.notifications,
    )
    service = ActivityNotificationService(
        activity_repository=activity,
        notifications=notifications,
        users=users,
        samples=samples,
        environment="production",
        sample_access=access,
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
        assert len(inbox.inbox(user=principal(username))["notifications"]) == 1
    repo.mark_read(str(source["_id"]), "group.reader")
    repo.create({**client.app.notifications.find_one(), "read_by": []})
    assert delivery.deliver() == 0
    assert inbox.inbox(user=principal("group.reader"))["notifications"][0]["read"]
    assert not inbox.inbox(user=principal("other.group"))["notifications"][0]["read"]


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
    assert (
        inbox.inbox(user=principal("group.reader"))["notifications"][0]["title"]
        == "Sample reported"
    )
    for username in ("other.group", "wrong.assay", "wrong.environment"):
        assert inbox.inbox(user=principal(username))["notifications"] == []


def test_matching_scope_without_clinical_read_permission_receives_no_report_notice():
    client, delivery, inbox, _ = fixture()
    delivery.users.list_active_users_for_notifications.return_value[0]["roles"] = []
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "sample", "report_num": 2})
    )
    delivery.deliver()
    assert inbox.inbox(user=principal("group.reader", roles=[]))["notifications"] == []
    assert "group.reader" not in client.app.notifications.find_one()["recipients"]


@pytest.mark.parametrize(
    "changes",
    [
        {"roles": []},
        {"asp_ids": ["another"]},
        {"asp_groups": ["solid"]},
        {"envs": ["testing"]},
    ],
)
def test_clinical_notice_is_hidden_after_access_revocation_but_broadcast_remains(changes):
    client, delivery, inbox, _ = fixture()
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "sample", "report_num": 2})
    )
    delivery.deliver()
    inbox.create_notification(
        audience="all",
        recipients=[],
        tone="info",
        category="application",
        title="Maintenance",
        message="Planned maintenance",
        source="Operations",
        created_by="system",
    )
    result = inbox.inbox(user=principal("group.reader", **changes))
    assert [row["title"] for row in result["notifications"]] == ["Maintenance"]
    assert "DEMO" not in str(result)
    assert "sample" not in str(result)


def test_inbox_rechecks_role_grants_and_deleted_sample_on_every_request():
    client, delivery, inbox, _ = fixture()
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "sample"})
    )
    delivery.deliver()
    assert inbox.inbox(user=principal("group.reader"))["notifications"]
    delivery.sample_access.roles.get_all_roles.return_value = []
    assert not inbox.inbox(user=principal("group.reader"))["notifications"]
    delivery.samples.get_notification_sample.return_value = None
    assert not inbox.inbox(user=principal("group.reader", roles=["superuser"]))["notifications"]


def test_inbox_pages_authorized_messages_after_hidden_clinical_rows():
    client, _, inbox, _ = fixture()
    now = datetime.now(timezone.utc)
    client.app.notifications.insert_many(
        [
            {
                "audience": "all",
                "created_on": now,
                "title": str(i),
                "resource": {"type": "sample", "id": "sample"} if i >= 4 else None,
            }
            for i in range(505)
        ]
    )
    first = inbox.inbox(user=principal("group.reader", roles=[]), limit=2)
    second = inbox.inbox(user=principal("group.reader", roles=[]), limit=2, offset=2)
    assert len(first["notifications"]) == len(second["notifications"]) == 2
    assert len({row["id"] for row in first["notifications"] + second["notifications"]}) == 4


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


def test_activity_pages_survive_restart_and_reconcile_late_events():
    client, service, _, _ = fixture()
    now = datetime.now(timezone.utc)
    client.identity.audit.insert_many(
        [event(occurred_at=now - timedelta(days=2)) for _ in range(60)]
    )
    assert service.deliver() == 16
    # A fresh repository resumes the persisted page instead of starting at the oldest row.
    service.activity = NotificationActivityRepository(
        audit_collection=client.identity.audit,
        operational_collection=client.identity.operational_audit_events,
        versions_collection=client.kb.versions,
        notifications=client.app.notifications,
    )
    assert service.deliver() == 16
    assert service.deliver() == 16
    assert service.deliver() == 12
    late = event(occurred_at=now - timedelta(days=3))
    client.identity.audit.insert_one(late)
    for _ in range(4):
        service.deliver()
    assert client.app.notifications.find_one({"_id": late["_id"]})
    assert client.app.notifications.count_documents({}) == 61


def test_unrelated_audit_history_advances_in_bounded_pages():
    client, service, _, _ = fixture()
    now = datetime.now(timezone.utc)
    client.identity.audit.insert_many([event("auth.login", occurred_at=now) for _ in range(60)])
    expected = event(occurred_at=now + timedelta(seconds=1))
    client.identity.audit.insert_one(expected)
    assert service.deliver() == 0
    assert service.deliver() == 0
    assert service.deliver() == 0
    assert service.deliver() == 1
    assert client.app.notifications.find_one({"_id": expected["_id"]})


def test_publication_cursor_handles_mixed_identifier_types_at_the_same_timestamp():
    client, service, _, _ = fixture()
    now = datetime.now(timezone.utc)
    client.kb.versions.insert_many(
        [
            {"_id": f"source-{index:02}", "published_at": now, "status": "active"}
            for index in range(25)
        ]
        + [{"_id": ObjectId(), "published_at": now, "status": "active"}]
    )
    assert service.deliver() == 16
    assert service.deliver() == 10
    assert service.deliver() == 0


def test_mark_unread_is_idempotent_and_recipient_scoped():
    client, delivery, inbox, repo = fixture()
    doc = event("report.saved", "report", metadata={"sample_oid": "sample"})
    client.identity.audit.insert_one(doc)
    delivery.deliver()
    identity = str(doc["_id"])
    repo.mark_read(identity, "group.reader")
    for _ in range(2):
        assert inbox.mark_unread(notification_id=identity, username="group.reader")["changed"] == 1
    assert not inbox.inbox(user=principal("group.reader"))["notifications"][0]["read"]
    with pytest.raises(AppError):
        inbox.mark_unread(notification_id=identity, username="other.group")


def test_missing_sample_never_broadcasts_report_identity():
    client, delivery, inbox, _ = fixture()
    delivery.samples.get_notification_sample.return_value = None
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": "deleted"})
    )
    assert delivery.deliver() == 1
    assert inbox.inbox(user=principal("group.reader"))["notifications"] == []


def test_report_notice_uses_current_assay_group_without_a_denormalized_sample_group():
    client, service, inbox, _ = fixture()
    identity = ObjectId()
    client.app.samples.insert_one(
        {
            "_id": identity,
            "name": "DEMO",
            "asp_id": "panel",
            "environment": "production",
            "asp_group": "stale",
        }
    )
    client.app.assays.insert_one({"asp_id": "panel", "asp_group": "hematology", "is_active": True})
    samples = SampleRepository(
        SimpleNamespace(samples_collection=client.app.samples, asp_collection=client.app.assays)
    )
    service.samples = samples
    service.sample_access.samples = samples
    client.identity.audit.insert_one(
        event("report.saved", "report", metadata={"sample_oid": str(identity)})
    )
    assert service.deliver() == 1
    assert inbox.inbox(user=principal("group.reader"))["notifications"]
    client.app.assays.update_one({}, {"$set": {"asp_group": "solid"}})
    assert not inbox.inbox(user=principal("group.reader"))["notifications"]
    client.app.assays.update_one({}, {"$set": {"is_active": False}})
    assert not inbox.inbox(user=principal("group.reader", asp_groups=["*"]))["notifications"]


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
