"""Tests for CLL-style observability and security infrastructure."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from coyote.application.common.request_context import (
    RequestContext,
    bind_request_context,
    reset_request_context,
)
from coyote_api.infra.observability.logging import JsonFormatter, request_context_from_request
from coyote_api.security import audit_events


def test_log_identity_uses_resolved_client_not_raw_forwarded_header():
    request = SimpleNamespace(
        headers={"X-Forwarded-For": "198.51.100.77"},
        client=SimpleNamespace(host="192.0.2.10"),
        method="GET",
        url=SimpleNamespace(path="/api/v1/auth/session"),
    )
    assert request_context_from_request(request).client_ip == "192.0.2.10"
    request.client = None
    assert request_context_from_request(request).client_ip is None


def test_access_audit_records_denials_only(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "coyote_api.app.deps.services.get_audit_service",
        lambda: SimpleNamespace(record=lambda *args, **kwargs: calls.append((args, kwargs))),
    )

    audit_events.emit_access_event(status="allowed", reason="OK", username="alice")
    assert calls == []

    audit_events.emit_access_event(
        status="denied",
        reason="Missing permission",
        username="alice",
        permission="sample:delete",
    )

    assert len(calls) == 1
    assert calls[0][0][0] == "security.access.denied"
    assert calls[0][1]["outcome"] == "denied"


def test_mutation_audit_uses_route_resource_metadata(monkeypatch):
    calls = []
    request = SimpleNamespace(
        method="DELETE",
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/api/v1/resources/samples/507f1f77bcf86cd799439011"),
        state=SimpleNamespace(
            audit_resource={
                "type": "sample",
                "id": "507f1f77bcf86cd799439011",
                "name": "CASE_DEMO",
                "message": "Deleted sample CASE_DEMO",
                "metadata": {"sample_oid": "507f1f77bcf86cd799439011"},
            }
        ),
    )

    monkeypatch.setattr(
        "coyote_api.app.deps.services.get_audit_service",
        lambda: SimpleNamespace(record=lambda *args, **kwargs: calls.append((args, kwargs))),
    )

    audit_events.emit_mutation_event(
        request=request,
        username="admin",
        status_code=200,
        action="DELETE",
        target="/api/v1/resources/samples/507f1f77bcf86cd799439011",
    )

    assert calls[0][0][0] == "api.mutation.succeeded"
    assert calls[0][0][1] == "Deleted sample CASE_DEMO"
    assert calls[0][1]["resource_type"] == "sample"
    assert calls[0][1]["resource_id"] == "507f1f77bcf86cd799439011"
    assert calls[0][1]["resource_name"] == "CASE_DEMO"
    assert calls[0][1]["metadata"]["sample_oid"] == "507f1f77bcf86cd799439011"
    assert calls[0][1]["retention_class"] == "operational"


def test_mutation_audit_preserves_traceability_retention_class(monkeypatch):
    calls = []
    request = SimpleNamespace(
        method="PUT",
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/api/v1/admin/asp/hema_gmsv1"),
        state=SimpleNamespace(
            audit_resource={
                "type": "asp",
                "id": "hema_gmsv1",
                "retention_class": "traceability",
                "metadata": {"previous_version": 1, "new_version": 2},
            }
        ),
    )
    monkeypatch.setattr(
        "coyote_api.app.deps.services.get_audit_service",
        lambda: SimpleNamespace(record=lambda *args, **kwargs: calls.append((args, kwargs))),
    )

    audit_events.emit_mutation_event(
        request=request,
        username="admin",
        status_code=200,
        action="PUT",
        target="/api/v1/admin/asp/hema_gmsv1",
    )

    assert calls[0][1]["retention_class"] == "traceability"
    assert calls[0][1]["metadata"]["previous_version"] == 1
    assert calls[0][1]["metadata"]["new_version"] == 2


def test_json_formatter_includes_bound_request_context():
    formatter = JsonFormatter()
    token = bind_request_context(
        RequestContext(
            request_id="rid-1",
            client_ip="127.0.0.1",
            method="POST",
            path="/api/v1/samples",
        )
    )
    try:
        record = logging.LogRecord(
            "coyote4.test",
            logging.INFO,
            __file__,
            1,
            "hello",
            (),
            None,
        )
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_context(token)

    assert payload["request_id"] == "rid-1"
    assert payload["client_ip"] == "127.0.0.1"
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/v1/samples"
