"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api.app.main import app as api_app
from api.domain.core.exceptions import AppError
from api.interfaces.http.clinical import samples
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
            "coverage.blacklist:manage",
        ],
        asp_ids=["WGS"],
        asp_groups=["dna"],
        envs=["production"],
        asp_map={},
        auth_type=["local"],
    )


def test_update_sample_filters_rejects_invalid_filters_payload():
    """Test update sample filters rejects invalid filters payload.

    Returns:
        The function result.
    """
    with pytest.raises(ValidationError) as exc:
        samples.SampleFiltersUpdateRequest.model_validate({"filters": "bad"})

    assert "Input should be a valid dictionary" in str(exc.value)


def test_bam_service_lookup_is_sample_scoped():
    """BAM-service lookup should be owned by the clinical sample API."""
    paths = {route.path for route in api_app.routes}

    assert "/api/v1/samples/{sample_name}/bam-files" in paths
    assert "/api/v1/knowledgebases/bam-files" not in paths


def test_sample_bam_files_read_returns_case_control_bam_paths(monkeypatch):
    """Sample BAM endpoint should resolve a sample name to case/control BAM paths."""
    service = SimpleNamespace(
        bam_files_payload=lambda *, sample_ids: {
            "query": {"sample_ids": sample_ids},
            "bam_files": {sample_id: [f"/bam/{sample_id}.bam"] for sample_id in sample_ids},
        }
    )
    sample = {
        "name": "CASE_DEMO",
        "case": {"id": "CASE1"},
        "control": {"id": "CTRL1"},
        "paired": True,
    }
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_name, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.sample_bam_files_read(
        sample_name="CASE_DEMO",
        user=fx.api_user(),
        service=service,
    )

    assert payload["sample"] == {
        "name": "CASE_DEMO",
        "case_id": "CASE1",
        "control_id": "CTRL1",
        "paired": True,
    }
    assert payload["bam_files"] == {
        "CASE1": ["/bam/CASE1.bam"],
        "CTRL1": ["/bam/CTRL1.bam"],
    }


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

    with pytest.raises(AppError) as exc:
        samples.reset_sample_filters("S1", user=fx.api_user())

    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "ASPC could not be resolved for the sample"
    assert exc.value.detail["category"] == "setup"


def test_apply_latest_aspc_replaces_a_sample_snapshot_explicitly(monkeypatch):
    """The route delegates the deliberate latest-ASPC transition to the service."""
    sample = {"_id": "sample-object-id", "name": "CASE_DEMO"}
    calls = {}

    def apply_latest_aspc(*, sample):
        calls["sample"] = sample
        return {"aspc_id": "hema_gmsv1_hem_production", "version": 3}

    service = SimpleNamespace(apply_latest_aspc=apply_latest_aspc)
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.apply_latest_sample_aspc(
        "CASE_DEMO",
        user=_route_test_user(),
        service=service,
    )

    assert calls["sample"] is sample
    assert payload["resource"] == "sample_aspc"
    assert payload["action"] == "apply_latest"
    assert payload["meta"]["applied_aspc"] == {
        "aspc_id": "hema_gmsv1_hem_production",
        "version": 3,
    }


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
        get_coverage_blacklist_entry=lambda *, obj_id: {"_id": obj_id, "group": "dna"},
        remove_coverage_blacklist=lambda *, obj_id: calls.setdefault("obj_id", obj_id),
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
