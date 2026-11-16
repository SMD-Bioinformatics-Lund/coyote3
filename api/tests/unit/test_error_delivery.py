"""Public error contracts and durable, redacted audit delivery."""

import json
import logging
from unittest.mock import Mock

import pytest
from coyote_api.infra.observability.logging import JsonFormatter, request_context_from_request
from coyote_api.interfaces.http.errors import ERROR_GUIDANCE, error_response
from coyote_api.interfaces.http.v1.operations.auth import http_exception_handler
from fastapi import HTTPException
from starlette.requests import Request


def request(headers=()):
    """Build an isolated synthetic HTTP request."""
    return Request({"type": "http", "method": "GET", "path": "/synthetic", "headers": headers})


@pytest.mark.parametrize("status", ERROR_GUIDANCE)
def test_error_contract_has_actionable_hint_and_support_reference(status):
    req = request()
    response = error_response(req, status, "Example", details="password=synthetic-secret")
    body = json.loads(response.body)
    assert response.status_code == body["status"] == status
    assert body["code"] == ERROR_GUIDANCE[status][0]
    assert body["hint"]
    assert body["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert "synthetic-secret" not in response.body.decode()
    if status >= 500:
        assert body["details"] is None
        assert body["error"] != "Example"


@pytest.mark.asyncio
async def test_http_exception_preserves_protocol_headers():
    result = await http_exception_handler(
        request(),
        HTTPException(
            405, detail="Unsupported method", headers={"Allow": "GET", "Retry-After": "10"}
        ),
    )
    assert result.headers["allow"] == "GET"
    assert result.headers["retry-after"] == "10"


def test_logging_redacts_credentials_in_messages_exceptions_and_nested_fields():
    record = logging.makeLogRecord(
        {
            "msg": "mongodb://synthetic-user:synthetic-password@mongo/db token=synthetic-token",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "exc_text": "Authorization: Bearer synthetic-bearer",
            "diagnostics": {"password": "synthetic-password"},
            "failure": ValueError("password=synthetic-object-secret"),
        }
    )
    rendered = JsonFormatter().format(record)
    for secret in ("synthetic-user", "synthetic-password", "synthetic-token", "synthetic-bearer"):
        assert secret not in rendered
    assert "[redacted]" in rendered
    assert "synthetic-object-secret" not in rendered


@pytest.mark.parametrize("identity", ["x" * 129, "bad\nheader", "", "token=secret"])
def test_untrusted_request_ids_are_replaced(identity):
    context = request_context_from_request(request([(b"x-request-id", identity.encode())]))
    assert context.request_id != identity
    assert len(context.request_id) == 36


@pytest.mark.asyncio
async def test_unhandled_error_preserves_actor_and_context_and_survives_audit_failure(monkeypatch):
    from coyote.application.common.request_context import current_request_context
    from coyote_api.app.main import unhandled_exception_handler

    req = request()
    req.state.request_id = "failure-reference"
    req.state.authenticated_user = "synthetic-user"
    recorder = Mock()

    def record(*args, **kwargs):
        assert kwargs["actor"] == "synthetic-user"
        assert current_request_context().request_id == "failure-reference"
        raise OSError("synthetic disk failure")

    recorder.record.side_effect = record
    monkeypatch.setattr("coyote_api.app.deps.services.get_audit_service", lambda: recorder)
    response = await unhandled_exception_handler(req, RuntimeError("private diagnostic"))
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failure-reference"
    assert b"private diagnostic" not in response.body
    recorder.record.assert_called_once()
