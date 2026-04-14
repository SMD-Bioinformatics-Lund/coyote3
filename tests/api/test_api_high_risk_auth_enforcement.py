"""High-risk API authn/authz behavior tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.main import app
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
    """Build a lightweight ApiUser for access checks."""
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role="user",
        roles=["user"],
        access_level=level,
        permissions=list(permissions or []),
        denied_permissions=list(denied or []),
        assays=["DNA", "RNA"],
        assay_groups=[],
        envs=["production"],
        asp_map={},
    )


def _resolve_access_dependency(method: str, path: str):
    """Resolve the require_access dependency callable for a route."""
    route = next(
        (
            entry
            for entry in app.router.routes
            if getattr(entry, "path", "") == path and method in getattr(entry, "methods", set())
        ),
        None,
    )
    assert route is not None
    dep = next(
        (
            entry.call
            for entry in route.dependant.dependencies
            if getattr(entry.call, "__name__", "") == "dep"
        ),
        None,
    )
    assert dep is not None
    return dep


def _request_for(path: str, method: str) -> Request:
    """Build a minimal request for dependency execution."""
    return Request({"type": "http", "method": method, "path": path, "headers": []})


@pytest.mark.parametrize(
    ("method", "path", "required_permission", "required_level"),
    [
        ("GET", "/api/v1/users", "user:list", 99999),
        ("GET", "/api/v1/roles", "role:list", 99999),
        ("GET", "/api/v1/permissions", "permission.policy:list", 99999),
        ("GET", "/api/v1/resources/aspc", "assay.config:list", 9),
        ("POST", "/api/v1/coverage/blacklist/entries", None, 1),
        ("GET", "/api/v1/samples/{sample_id}/reports/{report_type}/preview", "report:preview", 9),
    ],
)
def test_high_risk_endpoints_auth_matrix(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    required_permission: str | None,
    required_level: int,
):
    """Verify high-risk route access dependency behavior across auth scenarios."""
    monkeypatch.setattr(access, "_role_levels", lambda: ROLE_LEVELS)
    dep = _resolve_access_dependency(method=method, path=path)
    request = _request_for(path=path, method=method)

    def _raise_unauth(_request):
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})

    monkeypatch.setattr(access, "_decode_session_user", _raise_unauth)
    with pytest.raises(HTTPException) as unauth_exc:
        next(dep(request))
    assert unauth_exc.value.status_code == 401

    restricted_user = _user(level=max(0, required_level - 1), permissions=[])
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: restricted_user)
    with pytest.raises(HTTPException) as forbidden_exc:
        next(dep(request))
    assert forbidden_exc.value.status_code == 403

    allowed_permissions = [required_permission] if required_permission else []
    allowed_user = _user(level=max(required_level, 99999), permissions=allowed_permissions)
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: allowed_user)
    generator = dep(request)
    assert next(generator) == allowed_user
    generator.close()


def test_openapi_security_declares_auth_for_protected_routes():
    """Verify OpenAPI declares auth requirements for protected routes only."""
    schema = app.openapi()

    protected_operation = schema["paths"]["/api/v1/users"]["get"]
    assert {"ApiSessionCookie": []} in protected_operation.get("security", [])
    assert {"BearerAuth": []} in protected_operation.get("security", [])
    assert "401" in protected_operation.get("responses", {})
    assert "403" in protected_operation.get("responses", {})

    public_operation = schema["paths"]["/api/v1/public/assay-catalog/context"]["get"]
    assert "security" not in public_operation
