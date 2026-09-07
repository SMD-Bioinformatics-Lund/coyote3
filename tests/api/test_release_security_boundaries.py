"""Security regression tests across authentication and internal mutation boundaries."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.interfaces.http.operations.internal import (
    _enforce_collection_permission,
    _enforce_sample_ingest_permission,
)
from api.security.access import _enforce_password_change
from api.security.audit_events import request_ip


@pytest.mark.parametrize(
    "collection",
    ["users", "roles", "permissions", "samples", "variants", "annotation", "reported_variants"],
)
@pytest.mark.parametrize("action", ["create", "update"])
def test_raw_sensitive_import_cannot_bypass_owned_workflow(collection, action):
    with pytest.raises(HTTPException) as error:
        _enforce_collection_permission(
            user=SimpleNamespace(is_superuser=False), collection=collection, action=action
        )
    assert error.value.status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/samples"),
        ("POST", "/api/v1/internal/ingest/collection"),
        ("DELETE", "/api/v1/admin/clinical-rule-sets/drafts/id"),
        ("GET", "/api/v1/dashboard/summary"),
    ],
)
def test_temporary_password_cannot_access_clinical_or_admin_operations(method, path):
    request = Request({"type": "http", "method": method, "path": path, "headers": []})
    with pytest.raises(HTTPException) as error:
        _enforce_password_change(
            SimpleNamespace(must_change_password=True, is_superuser=True), request
        )
    assert error.value.detail["category"] == "password_change_required"


def test_temporary_password_can_be_changed_through_mounted_route():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/center/api/v1/auth/password/change",
            "root_path": "/center",
            "headers": [],
        }
    )
    _enforce_password_change(SimpleNamespace(must_change_password=True), request)


def test_untrusted_forwarded_header_does_not_change_audit_or_rate_limit_identity():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"192.0.2.10")],
            "client": ("127.0.0.1", 1234),
        }
    )
    assert request_ip(request) == "127.0.0.1"


def test_ingest_checks_assay_and_environment_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "api.interfaces.http.operations.internal._enforce_access",
        lambda user, **kwargs: captured.update(kwargs),
    )
    user = SimpleNamespace(is_superuser=False)
    _enforce_sample_ingest_permission(user, {"asp_id": "synthetic", "environment": "testing"})
    assert captured["context"] == {"asp_id": "synthetic", "environment": "testing"}
    with pytest.raises(HTTPException):
        _enforce_sample_ingest_permission(user, {"asp_id": "synthetic"})
