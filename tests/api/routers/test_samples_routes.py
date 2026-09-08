"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.routing import iter_route_contexts
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
    paths = {route.path for route in iter_route_contexts(api_app.routes)}

    assert "/api/v1/samples/{sample_name}/bam-files" in paths
    assert "/api/v1/knowledgebases/bam-files" not in paths


def test_coverage_mutation_rejects_out_of_scope_before_writing():
    user = SimpleNamespace(is_superuser=False, asp_groups=["allowed"], username="reviewer")
    with pytest.raises(AppError) as exc:
        samples.create_coverage_blacklist_entry(
            payload=samples.CoverageBlacklistUpdateRequest(
                gene="TP53", smp_grp="other", region="gene"
            ),
            user=user,
            service=SimpleNamespace(),
        )
    assert exc.value.status_code == 403


def test_coverage_delete_missing_entry_is_not_written():
    with pytest.raises(AppError) as exc:
        samples.delete_coverage_blacklist_entry(
            "missing",
            user=fx.api_user(),
            service=SimpleNamespace(get_coverage_blacklist_entry=lambda **kwargs: None),
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("file_type,attachment", [("html", False), ("html", True), ("pdf", True)])
def test_saved_report_files_are_served_with_correct_disposition(
    monkeypatch, tmp_path, file_type, attachment
):
    path = tmp_path / f"synthetic.{file_type}"
    path.write_bytes(b"synthetic report")
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda *args: {"name": "synthetic"})
    context = {"filepath": str(path), "pdf_filepath": str(path)}
    response = samples._sample_report_file_response(
        sample_id="synthetic",
        report_id="r1",
        user=fx.api_user(),
        service=SimpleNamespace(report_context_payload=lambda **kwargs: context),
        as_attachment=attachment,
        file_type=file_type,
    )
    assert response.media_type == ("application/pdf" if file_type == "pdf" else "text/html")
    if attachment:
        assert "attachment" in response.headers["content-disposition"]
    else:
        assert response.body == b"synthetic report"


@pytest.mark.parametrize("missing_path", [True, False])
def test_missing_saved_report_files_return_not_found(monkeypatch, tmp_path, missing_path):
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda *args: {"name": "synthetic"})
    context = {} if missing_path else {"filepath": str(tmp_path / "absent.html")}
    with pytest.raises(AppError) as exc:
        samples._sample_report_file_response(
            sample_id="synthetic",
            report_id="r1",
            user=fx.api_user(),
            service=SimpleNamespace(report_context_payload=lambda **kwargs: context),
            as_attachment=False,
        )
    assert exc.value.status_code == 404


def test_plot_file_resolution_rejects_symlink_escape(tmp_path):
    base = tmp_path / "plots"
    base.mkdir()
    private = tmp_path / "outside.txt"
    private.write_text("synthetic", encoding="utf-8")
    (base / "plot.txt").symlink_to(private)
    with pytest.raises(AppError) as exc:
        samples._safe_file_under(str(base), "plot.txt")
    assert exc.value.status_code == 400


def test_plot_file_resolution_requires_existing_configured_file(tmp_path):
    for base in (None, str(tmp_path)):
        with pytest.raises(AppError) as exc:
            samples._safe_file_under(base, "absent.txt")
        assert exc.value.status_code == 404
    file = tmp_path / "plot.txt"
    file.write_text("synthetic", encoding="utf-8")
    assert samples._safe_file_under(str(tmp_path), "plot.txt") == file


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
