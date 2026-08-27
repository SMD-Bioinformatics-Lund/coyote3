from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.notifications.service import NotificationService


class _UserRepository:
    def __init__(self, users):
        self.users = users

    def list_active_users_for_notifications(self, *, role_ids=None):
        rows = [row for row in self.users if row.get("is_active", True)]
        if role_ids:
            rows = [row for row in rows if set(row.get("roles") or []) & set(role_ids)]
        return sorted((dict(row) for row in rows), key=lambda row: row["username"])


class _NotificationRepository:
    def __init__(self):
        self.documents = []

    def create(self, document):
        document = dict(document)
        document["_id"] = f"notification-{len(self.documents) + 1}"
        self.documents.append(document)
        return document["_id"]

    def list_for_user(self, username, *, limit):
        return [
            row
            for row in self.documents
            if username not in row.get("dismissed_by", [])
            and (row.get("audience") == "all" or username in row.get("recipients", []))
        ][:limit]

    def mark_read(self, notification_id, username):
        for row in self.list_for_user(username, limit=500):
            if row["_id"] == notification_id:
                row.setdefault("read_by", []).append(username)
                return True
        return False

    def mark_all_read(self, username):
        rows = self.list_for_user(username, limit=500)
        for row in rows:
            row.setdefault("read_by", []).append(username)
        return len(rows)

    def dismiss(self, notification_id, username):
        for row in self.list_for_user(username, limit=500):
            if row["_id"] == notification_id:
                row.setdefault("dismissed_by", []).append(username)
                return True
        return False

    def dismiss_all(self, username):
        rows = self.list_for_user(username, limit=500)
        for row in rows:
            row.setdefault("dismissed_by", []).append(username)
        return len(rows)


def _service():
    notifications = _NotificationRepository()
    users = _UserRepository(
        [
            {"username": "admin", "roles": ["admin"], "is_active": True},
            {"username": "user.one", "roles": ["user"], "is_active": True},
            {"username": "user.two", "roles": ["user"], "is_active": True},
            {"username": "disabled", "roles": ["admin"], "is_active": False},
        ]
    )
    return NotificationService(
        notification_repository=notifications,
        user_repository=users,
        retention_days=30,
    ), notifications


def test_selected_broadcast_is_visible_only_to_selected_active_accounts():
    service, repository = _service()
    result = service.broadcast(
        payload={
            "audience": "selected",
            "recipients": ["user.one"],
            "tone": "info",
            "category": "feature",
            "title": "New review view",
            "message": "The updated review view is available.",
        },
        actor=SimpleNamespace(username="admin"),
    )

    assert result["recipient_count"] == 1
    assert len(service.inbox(username="user.one")["notifications"]) == 1
    assert service.inbox(username="user.two")["notifications"] == []
    assert repository.documents[0]["created_by"] == "admin"


def test_broadcast_rejects_unknown_or_inactive_selected_accounts():
    service, _ = _service()

    with pytest.raises(Exception, match="Unknown or inactive"):
        service.broadcast(
            payload={
                "audience": "selected",
                "recipients": ["disabled"],
                "title": "Maintenance",
                "message": "Maintenance is planned.",
            },
            actor=SimpleNamespace(username="admin"),
        )


def test_role_broadcast_materializes_active_users_in_selected_roles():
    service, repository = _service()

    result = service.broadcast(
        payload={
            "audience": "roles",
            "role_ids": ["user"],
            "tone": "info",
            "category": "application",
            "title": "Review workflow update",
            "message": "A review workflow update is available.",
        },
        actor=SimpleNamespace(username="admin"),
    )

    assert result["recipient_count"] == 2
    assert repository.documents[0]["audience"] == "users"
    assert repository.documents[0]["recipients"] == ["user.one", "user.two"]
    assert service.inbox(username="admin")["notifications"] == []
    assert len(service.inbox(username="user.one")["notifications"]) == 1


def test_recipient_options_include_active_role_counts():
    service, _ = _service()

    options = service.recipient_options()

    assert options["roles"] == [
        {"role_id": "admin", "label": "Admin", "user_count": 1},
        {"role_id": "user", "label": "User", "user_count": 2},
    ]


def test_password_reset_alert_targets_active_admin_accounts_only():
    service, repository = _service()

    notification_id = service.notify_password_reset_request(account_username="user.one")

    assert notification_id == "notification-1"
    assert repository.documents[0]["recipients"] == ["admin"]
    assert service.inbox(username="admin")["notifications"][0]["category"] == "security"
    assert service.inbox(username="user.one")["notifications"] == []


def test_read_and_dismissal_state_is_scoped_to_each_user():
    service, _ = _service()
    notification_id = service.create_notification(
        audience="all",
        recipients=[],
        tone="warning",
        category="maintenance",
        title="Maintenance",
        message="The service will restart.",
        source="Operations",
        created_by="admin",
    )

    service.mark_read(notification_id=notification_id, username="user.one")
    assert service.inbox(username="user.one")["notifications"][0]["read"] is True
    assert service.inbox(username="user.two")["notifications"][0]["read"] is False

    service.dismiss(notification_id=notification_id, username="user.one")
    assert service.inbox(username="user.one")["notifications"] == []
    assert len(service.inbox(username="user.two")["notifications"]) == 1
