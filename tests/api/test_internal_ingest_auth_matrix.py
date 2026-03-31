"""AuthN/AuthZ matrix tests for internal ingest routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routers import internal as internal_router
from api.security import access
from api.security.access import ApiUser
from api.services.ingest.service import InternalIngestService


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
        assays=["assay_1"],
        assay_groups=["hematology"],
        envs=["production"],
        asp_map={},
    )


def _resolve_access_dependency(method: str, path: str):
    route = next(
        (
            entry
            for entry in internal_router.router.routes
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
    return Request({"type": "http", "method": method, "path": path, "headers": []})


def test_internal_ingest_collection_requires_auth_and_admin(monkeypatch):
    """Collection ingest requires authenticated admin-level user."""
    monkeypatch.setattr(
        access, "_role_levels", lambda: {"viewer": 10, "developer": 50, "admin": 100}
    )
    monkeypatch.setattr(
        InternalIngestService,
        "insert_collection_document",
        lambda **_: {"status": "ok", "collection": "users", "inserted_count": 1},
    )
    dep = _resolve_access_dependency("POST", "/api/v1/internal/ingest/collection")
    request = _request_for("/api/v1/internal/ingest/collection", "POST")
    payload = internal_router.InternalCollectionInsertRequest(
        collection="users",
        document={
            "email": "admin@your-center.org",
            "role": "admin",
            "environments": ["production"],
        },
    )

    def _raise_unauth(_request):
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})

    monkeypatch.setattr(access, "_decode_session_user", _raise_unauth)
    with pytest.raises(HTTPException) as unauth_exc:
        next(dep(request))
    assert unauth_exc.value.status_code == 401

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="viewer", level=10),
    )
    with pytest.raises(HTTPException) as forbidden_exc:
        next(dep(request))
    assert forbidden_exc.value.status_code == 403

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="admin", level=100),
    )
    user = next(dep(request))
    result = internal_router.ingest_collection_document_internal(payload=payload, user=user)
    assert result["status"] == "ok"


def test_internal_ingest_sample_bundle_update_requires_edit_sample_permission(monkeypatch):
    """Update mode requires edit_sample for developer-level operators."""
    calls: dict[str, object] = {}

    def _ingest(payload, *, allow_update=False, increment=False):
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "S1",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        }

    monkeypatch.setattr(InternalIngestService, "ingest_sample_bundle", _ingest)
    payload = internal_router.InternalIngestSampleBundleRequest(
        sample={
            "name": "DEMO_SAMPLE_001",
            "assay": "assay_1",
            "subpanel": None,
            "profile": "testing",
            "case_id": "CASE_001",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipe",
            "pipeline_version": "v1",
            "vcf_files": "/tmp/demo.vcf",
        },
        update_existing=True,
    )

    with pytest.raises(HTTPException) as missing_perm_exc:
        internal_router.ingest_sample_bundle_internal(
            payload=payload,
            user=_user(role="developer", level=50, permissions=[]),
        )
    assert missing_perm_exc.value.status_code == 403

    response = internal_router.ingest_sample_bundle_internal(
        payload=payload,
        user=_user(role="developer", level=50, permissions=["edit_sample"]),
    )
    assert response["status"] == "ok"
    assert calls["allow_update"] is True
