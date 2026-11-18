# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Local callers cannot bypass the superuser boundary for session statistics."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.operations.administration import Users
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.auth import SessionActivitySummary
from coyote.domain.exceptions import AppError


@pytest.mark.parametrize("superuser", [False, True])
def test_session_counts_recheck_current_superuser_role_and_authentication(superuser):
    actor = SimpleNamespace(is_superuser=superuser, must_change_password=False)
    authenticate = Mock(return_value=actor)
    events = []
    runtime = ApplicationRuntime(
        authenticate=authenticate,
        policy_factory=lambda _: SimpleNamespace(permission_allowed=lambda *args, **kwargs: True),
        sample_loader=Mock(),
        assay_loader=Mock(),
        audit_access=events.append,
    )
    repository = Mock()
    repository.activity_summary.return_value = SessionActivitySummary(
        signed_in_users=2,
        active_sessions=3,
        recently_active_users=1,
        recent_activity_seconds=300,
        observed_at=datetime.now(timezone.utc),
    )
    factory = Mock(return_value=repository)
    users = Users(runtime, Mock(), factory)
    if superuser:
        assert users.session_activity().signed_in_users == 2
        assert events[-1].allowed is True
        actor.is_superuser = False
        factory.reset_mock()
    with pytest.raises(AppError) as denied:
        users.session_activity()
    assert denied.value.status_code == 403
    assert events[-1].allowed is False
    factory.assert_not_called()

    authenticate.return_value = None
    with pytest.raises(AppError) as expired:
        users.session_activity()
    assert expired.value.status_code == 401
    factory.assert_not_called()
