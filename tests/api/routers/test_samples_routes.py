"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.routing import iter_route_contexts
from pydantic import ValidationError

from api.app.main import app as api_app
from api.interfaces.http.v1.clinical import samples
from api.security.access import ApiUser
from coyote3.application.interpretation import report_summary
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
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


def test_sample_field_route_authorizes_before_returning_one_value(monkeypatch):
    """Sample metadata uses the normal sample authorization before service access."""
    paths = {route.path for route in iter_route_contexts(api_app.routes)}
    assert "/api/v1/samples/{sample_id}/fields/{field}" in paths
    assert "/api/v1/samples/{sample_id}/summary" not in paths
    sample = {"name": "DEMO_001"}
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    service = SimpleNamespace(sample_field=lambda received, field: received[field])
    assert (
        sdk_fixtures.invoke_route(
            samples.sample_field_read,
            "sample-1",
            "name",
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(service, fx.api_user(), "sample-1"),
        )
        == "DEMO_001"
    )


def test_sample_field_does_not_bypass_sample_access(monkeypatch):
    """Out-of-scope sample lookup fails before metadata is returned."""

    def denied(*args):
        raise AppError(status_code=403, message="Outside scope")

    monkeypatch.setattr(sdk_fixtures, "load_sample", denied)
    with pytest.raises(AppError) as error:
        sdk_fixtures.invoke_route(
            samples.sample_field_read,
            "other-sample",
            "name",
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(
                SimpleNamespace(sample_field=lambda *args: pytest.fail("Scope bypass")),
                fx.api_user(),
                "other-sample",
            ),
        )
    assert error.value.status_code == 403


def test_coverage_mutation_rejects_out_of_scope_before_writing():
    user = SimpleNamespace(is_superuser=False, asp_groups=["allowed"], username="reviewer")
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.create_coverage_blacklist_entry,
            payload=samples.CoverageBlacklistUpdateRequest(
                gene="TP53", smp_grp="other", region="gene"
            ),
            user=user,
            service=sdk_fixtures.coverage_operations(SimpleNamespace(), user),
        )
    assert exc.value.status_code == 403


def test_coverage_delete_missing_entry_is_not_written():
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.delete_coverage_blacklist_entry,
            "missing",
            user=fx.api_user(),
            service=sdk_fixtures.coverage_operations(
                SimpleNamespace(get_coverage_blacklist_entry=lambda **kwargs: None), fx.api_user()
            ),
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("file_type,attachment", [("html", False), ("html", True), ("pdf", True)])
def test_saved_report_files_are_served_with_correct_disposition(
    monkeypatch, tmp_path, file_type, attachment
):
    path = tmp_path / f"synthetic.{file_type}"
    path.write_bytes(b"synthetic report")
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *args: {"name": "synthetic"})
    context = {"filepath": str(path), "pdf_filepath": str(path)}
    response = sdk_fixtures.invoke_route(
        (
            samples.sample_report_pdf_download_read
            if file_type == "pdf"
            else samples.sample_report_download_read
            if attachment
            else samples.sample_report_html_read
        ),
        "synthetic",
        "r1",
        user=fx.api_user(),
        service=sdk_fixtures.sample_operations(
            SimpleNamespace(report_context_payload=lambda **kwargs: context),
            fx.api_user(),
            "synthetic",
        ),
    )
    assert response.media_type == ("application/pdf" if file_type == "pdf" else "text/html")
    assert response.headers["cache-control"] == "no-store"
    if file_type != "pdf":
        assert "sandbox;" in response.headers["content-security-policy"]
    if attachment:
        assert "attachment" in response.headers["content-disposition"]
    else:
        assert response.body == b"synthetic report"


@pytest.mark.parametrize("missing_path", [True, False])
def test_missing_saved_report_files_return_not_found(monkeypatch, tmp_path, missing_path):
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *args: {"name": "synthetic"})
    context = {} if missing_path else {"filepath": str(tmp_path / "absent.html")}
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.sample_report_html_read,
            "synthetic",
            "r1",
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(
                SimpleNamespace(report_context_payload=lambda **kwargs: context),
                fx.api_user(),
                "synthetic",
            ),
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("requested", ["other.png", "../registered.png", "absent.png"])
def test_plot_download_rejects_unregistered_names(monkeypatch, tmp_path, requested):
    monkeypatch.setattr("api.infra.artifact_paths.DATA_CONTAINER_ROOT", tmp_path)
    registered = tmp_path / "registered.png"
    registered.write_bytes(b"synthetic")
    (tmp_path / "other.png").write_bytes(b"other sample")
    monkeypatch.setattr(
        sdk_fixtures,
        "load_sample",
        lambda *_: {"files": {"cnvprofile": {"path": str(registered)}}},
    )
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.sample_plot_read,
            "authorized",
            requested,
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(SimpleNamespace(), fx.api_user(), "authorized"),
        )
    assert exc.value.status_code == 404


def test_plot_download_requires_registered_artifact(monkeypatch):
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *_: {"files": {}})
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.sample_plot_read,
            "authorized",
            "other.png",
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(SimpleNamespace(), fx.api_user(), "authorized"),
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("suffix,expected", [("png", 200), ("html", 415), ("svg", 415)])
def test_plot_download_allows_only_registered_raster_images(
    monkeypatch, tmp_path, suffix, expected
):
    monkeypatch.setattr("api.infra.artifact_paths.DATA_CONTAINER_ROOT", tmp_path)
    registered = tmp_path / f"registered.{suffix}"
    registered.write_bytes(b"synthetic")
    monkeypatch.setattr(
        sdk_fixtures,
        "load_sample",
        lambda *_: {"files": {"cnvprofile": {"path": str(registered)}}},
    )
    if expected == 415:
        with pytest.raises(AppError) as exc:
            sdk_fixtures.invoke_route(
                samples.sample_plot_read,
                "authorized",
                registered.name,
                user=fx.api_user(),
                service=sdk_fixtures.sample_operations(
                    SimpleNamespace(), fx.api_user(), "authorized"
                ),
            )
        assert exc.value.status_code == 415
    else:
        response = sdk_fixtures.invoke_route(
            samples.sample_plot_read,
            "authorized",
            registered.name,
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(SimpleNamespace(), fx.api_user(), "authorized"),
        )
        assert Path(response.path) == registered
        assert response.media_type == "image/png"
        assert response.headers["cache-control"] == "no-store"


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
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_name, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        samples.sample_bam_files_read,
        sample_name="CASE_DEMO",
        user=fx.api_user(),
        service=sdk_fixtures.sample_operations(service, fx.api_user(), "CASE_DEMO"),
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
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    monkeypatch.setattr(sdk_fixtures, "configuration", lambda _sample: None)

    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            samples.reset_sample_filters,
            "S1",
            user=fx.api_user(),
            service=sdk_fixtures.sample_operations(SimpleNamespace(), fx.api_user(), "S1"),
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "ASPC could not be resolved for the sample"
    assert exc.value.detail["category"] == "setup"


def test_apply_latest_aspc_replaces_a_sample_snapshot_explicitly(monkeypatch):
    """The route delegates the deliberate latest-ASPC transition to the service."""
    sample = {"_id": "sample-object-id", "name": "CASE_DEMO"}
    calls = {}

    def apply_latest_aspc(*, sample, **options):
        calls["sample"] = sample
        calls["options"] = options
        return {"aspc_id": "hema_gmsv1_hem_production", "version": 3}

    service = SimpleNamespace(apply_latest_aspc=apply_latest_aspc)
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        samples.apply_latest_sample_aspc,
        "CASE_DEMO",
        payload=samples.ConfigurationApplyRequest(
            expected_version=2, configuration_id="release-3", reason="Validated release"
        ),
        user=_route_test_user(),
        service=sdk_fixtures.sample_operations(service, _route_test_user(), "CASE_DEMO"),
    )

    assert calls["sample"] == sample
    assert calls["sample"] is not sample
    assert calls["options"]["expected_version"] == 2
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

    payload = sdk_fixtures.invoke_route(
        samples.create_coverage_blacklist_entry,
        payload=samples.CoverageBlacklistUpdateRequest(
            gene="TP53", status="blacklisted", smp_grp="dna", region="gene"
        ),
        user=fx.api_user(),
        service=sdk_fixtures.coverage_operations(service, fx.api_user()),
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

    payload = sdk_fixtures.invoke_route(
        samples.delete_coverage_blacklist_entry,
        "abc123",
        user=fx.api_user(),
        service=sdk_fixtures.coverage_operations(service, fx.api_user()),
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
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(
        report_summary,
        "create_comment_doc",
        lambda form_data, key="sample_comment": {"key": key, **form_data},
    )

    payload = sdk_fixtures.invoke_route(
        samples.create_sample_comment,
        "S1",
        payload=samples.SampleCommentCreateRequest(form_data={"comment": "hello"}),
        user=fx.api_user(),
        service=sdk_fixtures.sample_operations(service, fx.api_user(), "S1"),
    )

    assert calls["sample_id"] == "S1"
    assert payload["resource"] == "sample_comment"
