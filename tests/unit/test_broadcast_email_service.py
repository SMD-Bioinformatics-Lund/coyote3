"""Test email workflow decisions without MongoDB or SMTP."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.application.notifications.service import NotificationService


@pytest.mark.parametrize(
    ("active", "address", "sent", "state"),
    [
        (True, "reader@example.test", True, "sent"),
        (True, "reader@example.test", False, "failed"),
        (False, "reader@example.test", True, "skipped"),
        (True, "", True, "skipped"),
    ],
)
def test_email_outcome_and_minimal_message(active, address, sent, state):
    repo = Mock()
    repo.claim_email.side_effect = [
        (
            {"_id": "notice"},
            {
                "username": "reader",
                "lease_id": "lease",
                "attempts": 1,
            },
        ),
        None,
    ]
    sender = Mock(return_value=sent)
    users = SimpleNamespace(user_with_id=lambda username: {"is_active": active, "email": address})
    service = NotificationService(
        notification_repository=repo,
        user_repository=users,
        retention_days=30,
        email_sender=sender,
        inbox_url="https://coyote3.example.test/notifications",
    )
    assert service.deliver_emails()[state] == 1
    repo.finish_email.assert_called_once_with("notice", "lease", state=state)
    if state != "skipped":
        assert sender.call_args.kwargs["to_email"] == address
        assert service.inbox_url in sender.call_args.kwargs["text_body"]
    else:
        sender.assert_not_called()


def test_no_transport_does_not_claim_jobs():
    repo = Mock()
    service = NotificationService(
        notification_repository=repo, user_repository=Mock(), retention_days=30
    )
    assert service.deliver_emails()["status"] == "not_configured"
    repo.claim_email.assert_not_called()
