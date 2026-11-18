# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP session statistics require superuser membership, not just user-list access."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from api_test_support.mock_collections import api_user
from coyote.application.operations.administration import Users
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.auth import SessionActivitySummary
from coyote.domain.exceptions import AppError
from coyote_api.app.deps.application import get_users
from coyote_api.interfaces.http.v1.admin.users import router
from coyote_api.security import access
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.fixture
def boundary(monkeypatch):
    user = api_user()
    user.roles = ["sys_admin"]
    user.permissions = ["user:list"]
    identity = Mock(return_value=user)

    def decode(request):
        actor = identity()
        if actor is None:
            raise HTTPException(401, "Login required")
        return actor

    policy = SimpleNamespace(
        permission_allowed=lambda actor, permission, **kwargs: permission in actor.permissions
    )
    monkeypatch.setattr(access, "_decode_session_user", decode)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    monkeypatch.setattr(access, "get_roles_repository", lambda: None)
    monkeypatch.setattr(access, "get_permissions_repository", lambda: None)
    monkeypatch.setattr(access, "build_access_policy", lambda **kwargs: policy)
    repository = Mock()
    repository.activity_summary.return_value = SessionActivitySummary(
        signed_in_users=2,
        active_sessions=3,
        recently_active_users=1,
        recent_activity_seconds=300,
        observed_at=datetime.now(timezone.utc),
    )
    runtime = ApplicationRuntime(
        authenticate=identity,
        policy_factory=lambda _: policy,
        sample_loader=Mock(),
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    users = Users(runtime, Mock(), lambda: repository, Mock())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_users] = lambda: users

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    with TestClient(app) as client:
        yield client, user, identity, repository


def test_session_activity_blocks_admins_and_anonymous_callers(boundary):
    client, user, identity, repository = boundary
    assert client.get("/api/v1/users/session-activity").status_code == 403
    user.permissions = []
    assert client.get("/api/v1/users/session-activity").status_code == 403
    identity.return_value = None
    assert client.get("/api/v1/users/session-activity").status_code == 401
    repository.activity_summary.assert_not_called()


def test_superuser_gets_uncached_counts_and_loses_access_when_demoted(boundary):
    client, user, identity, repository = boundary
    user.roles = ["superuser"]
    response = client.get("/api/v1/users/session-activity")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "signed_in_users": 2,
        "active_sessions": 3,
        "recently_active_users": 1,
        "recent_activity_seconds": 300,
        "observed_at": repository.activity_summary.return_value.model_dump(mode="json")[
            "observed_at"
        ],
    }
    user.roles = ["sys_admin"]
    assert client.get("/api/v1/users/session-activity").status_code == 403
    assert repository.activity_summary.call_count == 1
