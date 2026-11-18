# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Recovery dispatch, non-disclosure and administrator authorization regressions."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.accounts.recovery import AccountRecoveryService
from coyote.application.operations.account import PasswordRecovery
from coyote.application.operations.administration import Users
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.domain.exceptions import AppError


def service(user):
    repository, notifications, token, audit = Mock(), Mock(), Mock(), Mock()
    repository.user_by_username.return_value = user
    repository.request_recovery.side_effect = lambda username, record: record
    notifications.user_repository.list_active_users_for_notifications.return_value = [
        {"username": "admin"}
    ]
    return AccountRecoveryService(repository, notifications, token, audit)


@pytest.mark.parametrize("user", [None, {"is_active": False, "auth_type": ["local"]}])
def test_unknown_and_inactive_accounts_do_not_send_or_write(user):
    workflow = service(user)
    assert workflow.request(login_identifier="unknown") == {"status": "ok"}
    workflow.issue_token.assert_not_called()
    workflow.repository.request_recovery.assert_not_called()
    workflow.notifications.create_notification.assert_not_called()


def test_local_username_uses_existing_delivery_only():
    workflow = service({"auth_type": ["local"], "email": "synthetic@example.invalid"})
    workflow.request(login_identifier=" Synthetic ")
    workflow.repository.user_by_username.assert_called_once_with("synthetic")
    workflow.issue_token.assert_called_once_with(
        login_identifier="synthetic", purpose="reset", actor_username=None
    )
    workflow.repository.request_recovery.assert_not_called()


@pytest.mark.parametrize("provider,email", [("ldap", "person@example.invalid"), ("local", "")])
def test_assisted_recovery_queues_email_and_inbox_without_password(provider, email):
    workflow = service({"auth_type": [provider], "email": email})
    workflow.request(login_identifier="synthetic")
    workflow.issue_token.assert_not_called()
    record = workflow.repository.request_recovery.call_args.args[1]
    assert record["provider"] == provider
    assert record["status"] == "pending"
    assert not any("token" in key or "password" in key for key in record)
    notice = workflow.notifications.create_notification.call_args.kwargs
    assert notice["recipients"] == notice["email_recipients"] == ["admin"]


def test_mixed_provider_account_can_request_ldap_explicitly():
    workflow = service({"auth_type": ["local", "ldap"], "email": "person@example.invalid"})
    workflow.request(login_identifier="synthetic", provider="ldap")
    workflow.issue_token.assert_not_called()
    assert workflow.repository.request_recovery.call_args.args[1]["provider"] == "ldap"


def test_notification_retry_keeps_same_request_identity():
    workflow = service({"auth_type": ["ldap"]})
    record = dict(
        request_id="r1",
        username="synthetic",
        provider="ldap",
        requested_at=datetime.now(timezone.utc),
    )
    workflow.repository.request_recovery.side_effect = None
    workflow.repository.request_recovery.return_value = record
    workflow.request(login_identifier="synthetic")
    workflow.request(login_identifier="synthetic")
    ids = [
        call.kwargs["event_id"]
        for call in workflow.notifications.create_notification.call_args_list
    ]
    assert ids == ["password-recovery:r1:requested"] * 2


def test_completion_notifies_owner_and_records_original_actor_on_retry():
    workflow = service({"auth_type": ["ldap"]})
    workflow.repository.complete_recovery.return_value = dict(
        request_id="r1",
        username="synthetic",
        provider="ldap",
        status="completed",
        requested_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        completed_by="first-admin",
    )
    assert workflow.complete("r1", "retry-admin").completed_by == "first-admin"
    notice = workflow.notifications.create_notification.call_args.kwargs
    assert notice["recipients"] == notice["email_recipients"] == ["synthetic"]
    assert notice["created_by"] == "first-admin"
    workflow.issue_token.assert_not_called()


def test_missing_or_changed_account_cannot_complete():
    workflow = service(None)
    workflow.repository.complete_recovery.return_value = None
    with pytest.raises(AppError) as error:
        workflow.complete("r1", "admin")
    assert error.value.status_code == 409
    workflow.notifications.create_notification.assert_not_called()


def test_delivery_failure_does_not_disclose_account_existence():
    request = Mock(side_effect=RuntimeError("private delivery detail"))
    operation = PasswordRecovery(request_token=request, consume_token=Mock())
    assert operation.request_reset("synthetic") == {"status": "ok"}


@pytest.mark.parametrize(
    "roles,permitted",
    [(["user"], False), (["admin"], False), (["sys_admin"], True), (["superuser"], True)],
)
def test_assisted_recovery_requires_account_administrator_even_with_edit_grant(roles, permitted):
    actor = SimpleNamespace(
        username="operator",
        roles=roles,
        is_superuser="superuser" in roles,
        must_change_password=False,
    )
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=lambda _: SimpleNamespace(permission_allowed=lambda *a, **k: True),
        sample_loader=Mock(),
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    recovery = Mock()
    recovery.pending.return_value = []
    users = Users(runtime, Mock(), Mock(), lambda: recovery)
    if permitted:
        assert users.recovery_requests() == []
    else:
        with pytest.raises(AppError):
            users.recovery_requests()
        with pytest.raises(AppError):
            users.complete_recovery("r1")
        recovery.pending.assert_not_called()
        recovery.complete.assert_not_called()


def test_completion_email_uses_security_sender_and_contains_no_credentials():
    from coyote.application.notifications.service import NotificationService

    repository = Mock()
    repository.claim_email.side_effect = [
        (
            {
                "_id": "notice",
                "source": "Account recovery",
                "category": "security",
                "title": "Password recovery completed",
                "message": "An administrator confirmed recovery completed.",
            },
            {"username": "person", "attempts": 1, "lease_id": "lease"},
        ),
        None,
    ]
    users = Mock()
    users.user_with_id.return_value = {"email": "person@example.invalid", "is_active": True}
    sender = Mock(return_value=True)
    notifications = NotificationService(
        notification_repository=repository,
        user_repository=users,
        retention_days=30,
        email_sender=sender,
        inbox_url="https://example.invalid/notifications",
    )
    notifications.deliver_emails()
    email = sender.call_args.kwargs
    assert email["purpose"] == "security"
    assert "confirmed recovery completed" in email["text_body"]
    assert email["to_email"] == "person@example.invalid"
    repository.finish_email.assert_called_once_with("notice", "lease", state="sent")
