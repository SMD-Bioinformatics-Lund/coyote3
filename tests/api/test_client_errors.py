"""Browser diagnostics require authentication and bounded input."""

import logging
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.interfaces.http.operations.client_errors import router


def test_client_errors_require_authentication_and_validate_payload(monkeypatch, caplog):
    import api.security.access as access

    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)

    def unauthenticated(request):
        raise HTTPException(401, "Sign in")

    monkeypatch.setattr(access, "_decode_session_user", unauthenticated)
    client = TestClient(app)
    assert client.post("/api/v1/client-errors", json={"message": "failed"}).status_code == 401
    dependency = router.routes[0].dependant.dependencies[0].call
    app.dependency_overrides[dependency] = lambda: SimpleNamespace(username="synthetic-user")
    assert client.post("/api/v1/client-errors", json={"message": "x" * 4001}).status_code == 422
    with caplog.at_level(logging.ERROR, logger="coyote.ui"):
        response = client.post(
            "/api/v1/client-errors", json={"message": "render failed", "stack": "test stack"}
        )
    assert response.status_code == 200
    assert caplog.records[-1].actor == "synthetic-user"
    assert caplog.records[-1].exception == "test stack"
