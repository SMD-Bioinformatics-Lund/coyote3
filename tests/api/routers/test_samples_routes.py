"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.routers import samples
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
        roles=["manager"],
        access_level=99,
        permissions=[
            "sample:edit:own",
            "sample.comment:add",
            "sample.comment:hide",
            "sample.comment:unhide",
        ],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
    )


def test_update_sample_filters_rejects_invalid_filters_payload():
    """Test update sample filters rejects invalid filters payload.

    Returns:
        The function result.
    """
    with pytest.raises(ValidationError) as exc:
        samples.SampleFiltersUpdateRequest.model_validate({"filters": "bad"})

    assert "Input should be a valid dictionary" in str(exc.value)


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

    with pytest.raises(HTTPException) as exc:
        samples.reset_sample_filters("S1", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Assay config not found for sample"


def test_update_coverage_blacklist_gene_returns_change_payload(monkeypatch):
    """Create coverage blacklist entry should return a standard change payload."""
    calls = {}
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    service = SimpleNamespace(
        add_coverage_blacklist=lambda gene, coord, region, smp_grp: calls.setdefault(
            "gene", (gene, smp_grp)
        )
    )

    payload = samples.create_coverage_blacklist_entry(
        payload=samples.CoverageBlacklistUpdateRequest(
            gene="TP53", status="blacklisted", smp_grp="dna", region="gene"
        ),
        user=fx.api_user(),
        service=service,
    )

    assert calls["gene"] == ("TP53", "dna")
    assert payload["status"] == "ok"
    assert payload["resource"] == "blacklist"
    assert payload["resource_id"] == "TP53:gene"
    assert payload["action"] == "add"


def test_remove_coverage_blacklist_returns_change_payload(monkeypatch):
    """Delete coverage blacklist helper should keep the route contract payload."""
    calls = {}
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    service = SimpleNamespace(
        remove_coverage_blacklist=lambda *, obj_id: calls.setdefault("obj_id", obj_id)
    )

    payload = samples.delete_coverage_blacklist_entry(
        "abc123",
        user=fx.api_user(),
        service=service,
    )

    assert calls["obj_id"] == "abc123"
    assert payload["resource"] == "blacklist"
    assert payload["resource_id"] == "abc123"
    assert payload["action"] == "remove"


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
    service = SimpleNamespace(
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
        service=service,
    )

    assert calls["sample_id"] == "S1"
    assert payload["resource"] == "sample_comment"
