"""AuthN/AuthZ matrix tests for internal ingest routes."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app
from api.security import access
from api.security.access import ApiUser
from api.services.internal_ingest_service import InternalIngestService


def _user(*, role: str, level: int, permissions: list[str] | None = None) -> ApiUser:
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role=role,
        access_level=level,
        permissions=list(permissions or []),
        denied_permissions=[],
        assays=["ASSAY_A"],
        assay_groups=["GROUP_A"],
        envs=["production"],
        asp_map={},
    )


def test_internal_ingest_collection_requires_auth_and_admin(monkeypatch):
    """Collection ingest requires authenticated admin-level user."""
    monkeypatch.setattr(access, "_role_levels", lambda: {"viewer": 10, "admin": 100})
    monkeypatch.setattr(
        InternalIngestService,
        "insert_collection_document",
        lambda **_: {"status": "ok", "collection": "users", "inserted_count": 1},
    )
    client = TestClient(app)
    payload = {
        "collection": "users",
        "document": {
            "email": "admin@center.local",
            "role": "admin",
            "environments": ["production"],
        },
    }

    def _raise_unauth(_request):
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})

    monkeypatch.setattr(access, "_decode_session_user", _raise_unauth)
    assert client.post("/api/v1/internal/ingest/collection", json=payload).status_code == 401

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="viewer", level=10),
    )
    assert client.post("/api/v1/internal/ingest/collection", json=payload).status_code == 403

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="admin", level=100),
    )
    assert client.post("/api/v1/internal/ingest/collection", json=payload).status_code == 200


def test_internal_ingest_sample_bundle_update_requires_edit_sample_permission(monkeypatch):
    """Update mode requires edit_sample permission even for admin role."""
    monkeypatch.setattr(access, "_role_levels", lambda: {"admin": 100})
    calls: dict[str, object] = {}

    def _ingest(payload, *, allow_update=False):
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "S1",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        }

    monkeypatch.setattr(InternalIngestService, "ingest_sample_bundle", _ingest)
    client = TestClient(app)
    payload = {"spec": {"name": "DEMO_SAMPLE_001"}, "update_existing": True}

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="admin", level=100, permissions=[]),
    )
    assert client.post("/api/v1/internal/ingest/sample-bundle", json=payload).status_code == 403

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="admin", level=100, permissions=["edit_sample"]),
    )
    response = client.post("/api/v1/internal/ingest/sample-bundle", json=payload)
    assert response.status_code == 200
    assert calls["allow_update"] is True
