"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deps.repositories import get_sample_repository
from api.main import app as api_app
from api.routers import samples
from api.security import access
from api.security.access import ApiUser
from tests.fixtures.api import mock_collections as fx


def _route_test_user() -> ApiUser:
    """Route test user.

    Returns:
            The  route test user result.
    """
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="manager",
        access_level=99,
        permissions=[
            "edit_sample",
            "add_sample_comment",
            "hide_sample_comment",
            "unhide_sample_comment",
        ],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
    )


def test_update_sample_filters_rejects_invalid_filters_payload(monkeypatch):
    """Test update sample filters rejects invalid filters payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["_id"] = "S1"
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)
    api_app.dependency_overrides[get_sample_repository] = lambda: SimpleNamespace()
    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.put("/api/v1/samples/S1/filters", json={"filters": "bad"})
    api_app.dependency_overrides.pop(get_sample_repository, None)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "Validation failed"


def test_reset_sample_filters_requires_assay_config(monkeypatch):
    """Test reset sample filters requires assay config.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(samples, "get_formatted_assay_config", lambda _sample: None)
    repository = SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        samples.reset_sample_filters("S1", user=fx.api_user(), repository=repository)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Assay config not found for sample"


def test_update_coverage_blacklist_gene_returns_status_message(monkeypatch):
    """Test update coverage blacklist gene returns status message.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {}
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    repository = SimpleNamespace(
        blacklist_gene=lambda gene, smp_grp: calls.setdefault("gene", (gene, smp_grp))
    )

    payload = samples.create_coverage_blacklist_entry(
        payload=samples.CoverageBlacklistUpdateRequest(
            gene="TP53", status="blacklisted", smp_grp="dna", region="gene"
        ),
        user=fx.api_user(),
        repository=repository,
    )

    assert calls["gene"] == ("TP53", "dna")
    assert payload["status"] == "ok"
    assert "TP53" in payload["message"]


def test_restful_sample_comment_route_creates_comment(monkeypatch):
    """Test restful sample comment route creates comment.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["_id"] = "S1"
    calls = {}
    repository = SimpleNamespace(
        add_sample_comment=lambda sample_id, doc: calls.setdefault("sample_id", sample_id)
    )
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(
        samples,
        "create_comment_doc",
        lambda form_data, key="sample_comment": {"key": key, **form_data},
    )

    payload = samples.create_sample_comment(
        "S1",
        payload=samples.SampleCommentCreateRequest(form_data={"comment": "hello"}),
        user=fx.api_user(),
        repository=repository,
    )

    assert calls["sample_id"] == "S1"
    assert payload["resource"] == "sample_comment"
