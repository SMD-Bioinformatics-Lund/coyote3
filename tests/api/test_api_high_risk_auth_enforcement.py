"""High-risk API authn/authz behavior tests."""

from __future__ import annotations

from typing import Callable
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deps.repositories import get_sample_repository
from api.main import app
from api.routers import admin_resources as admin
from api.routers import permissions, roles, users
from api.routers import reports
from api.routers import samples
from api.security import access
from api.security.access import ApiUser

ROLE_LEVELS = {
    "user": 9,
    "manager": 99,
    "admin": 99999,
    "developer": 9999,
}


def _user(
    *, level: int, permissions: list[str] | None = None, denied: list[str] | None = None
) -> ApiUser:
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role="user",
        access_level=level,
        permissions=list(permissions or []),
        denied_permissions=list(denied or []),
        assays=["DNA", "RNA"],
        assay_groups=[],
        envs=["production"],
        asp_map={},
    )


def _setup_admin_list_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        users.get_admin_user_service,
        lambda: SimpleNamespace(list_users_payload=lambda: {"users": [], "roles": {}}),
    )
    monkeypatch.setattr(users.util.common, "convert_to_serializable", lambda payload: payload)


def _setup_admin_list_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        roles.get_admin_role_service,
        lambda: SimpleNamespace(list_roles_payload=lambda: {"roles": []}),
    )
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)


def _setup_admin_list_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        permissions.get_admin_permission_service,
        lambda: SimpleNamespace(
            list_permissions_payload=lambda: {"permission_policies": [], "grouped_permissions": {}}
        ),
    )
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)


def _setup_admin_list_aspc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        admin.get_admin_aspc_service,
        lambda: SimpleNamespace(list_payload=lambda: {"assay_configs": []}),
    )
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)


def _setup_samples_blacklist_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        get_sample_repository,
        lambda: SimpleNamespace(blacklist_coord=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)


def _setup_reports_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: ({"_id": sample_id, "name": sample_id}, {"_id": "A1"}),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        reports, "_build_preview_report", lambda *args, **kwargs: ("dna_report.html", {}, [])
    )
    monkeypatch.setattr(
        reports,
        "_preview_response_payload",
        lambda **kwargs: {
            "sample": {"id": "S1", "name": "S1", "assay": "DNA", "profile": "production"},
            "meta": {
                "request_path": "/api/v1/dna/samples/S1/reports/preview",
                "include_snapshot": False,
                "snapshot_count": 0,
            },
            "report": {"template": "dna_report.html", "context": {}, "snapshot_rows": []},
        },
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)


_EndpointSetup = Callable[[pytest.MonkeyPatch], None]


@pytest.mark.parametrize(
    ("method", "path", "payload", "required_permission", "required_level", "setup"),
    [
        ("GET", "/api/v1/admin/users", None, "view_user", 99999, _setup_admin_list_users),
        ("GET", "/api/v1/admin/roles", None, "view_role", 99999, _setup_admin_list_roles),
        (
            "GET",
            "/api/v1/admin/permissions",
            None,
            "view_permission_policy",
            99999,
            _setup_admin_list_permissions,
        ),
        ("GET", "/api/v1/admin/aspc", None, "view_aspc", 9, _setup_admin_list_aspc),
        (
            "POST",
            "/api/v1/coverage/blacklist/entries",
            {
                "gene": "TP53",
                "coord": "17:1-2",
                "region": "coding",
                "smp_grp": "G",
                "status": "blacklisted",
            },
            None,
            1,
            _setup_samples_blacklist_update,
        ),
        (
            "GET",
            "/api/v1/dna/samples/S1/reports/preview",
            None,
            "preview_report",
            9,
            _setup_reports_preview,
        ),
    ],
)
def test_high_risk_endpoints_auth_matrix(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict | None,
    required_permission: str | None,
    required_level: int,
    setup: _EndpointSetup,
):
    setup(monkeypatch)
    monkeypatch.setattr(access, "_role_levels", lambda: ROLE_LEVELS)
    client = TestClient(app)

    def _request() -> int:
        kwargs = {"json": payload} if payload is not None else {}
        return client.request(method, path, **kwargs).status_code

    # 1) Unauthenticated -> 401
    def _raise_unauth(_request):
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})

    monkeypatch.setattr(access, "_decode_session_user", _raise_unauth)
    assert _request() == 401

    # 2) Authenticated but restricted -> 403
    restricted_user = _user(level=max(0, required_level - 1), permissions=[])
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: restricted_user)
    assert _request() == 403

    # 3) Authenticated and permitted -> 200
    allowed_permissions = [required_permission] if required_permission else []
    allowed_user = _user(level=max(required_level, 99999), permissions=allowed_permissions)
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: allowed_user)
    assert _request() == 200


def test_openapi_security_declares_auth_for_protected_routes():
    client = TestClient(app)
    schema = client.get("/api/v1/openapi.json").json()

    protected_operation = schema["paths"]["/api/v1/admin/users"]["get"]
    assert {"ApiSessionCookie": []} in protected_operation.get("security", [])
    assert {"BearerAuth": []} in protected_operation.get("security", [])
    assert "401" in protected_operation.get("responses", {})
    assert "403" in protected_operation.get("responses", {})

    public_operation = schema["paths"]["/api/v1/public/assay-catalog/context"]["get"]
    assert "security" not in public_operation
