"""Behavior tests for report API routes (preview/save)."""

from __future__ import annotations

import pytest

from api.app.main import app as api_app
from api.domain.core.exceptions import AppError
from api.interfaces.http.clinical.reporting import reports
from api.security.access import ApiUser


def _user(username: str = "tester", role: str = "admin") -> ApiUser:
    """User.

    Args:
            username: Username. Optional argument.
            role: Role. Optional argument.

    Returns:
            The  user result.
    """
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username=username,
        role=role,
        roles=[role],
        access_level=99,
        permissions=["report:preview", "report:create"],
        asp_ids=["WGS"],
        asp_groups=["dna", "rna"],
        envs=["dev"],
        asp_map={},
        auth_type=["local"],
    )


def test_report_validation_rejects_analyte_that_does_not_match_sample_modality():
    """Reject a DNA report request for an RNA sample before workflow rendering."""
    with pytest.raises(AppError) as exc_info:
        reports._validate_report_inputs(
            "dna",
            {"name": "RNA_SAMPLE", "omics_layer": "rna"},
            {"analysis_types": ["FUSION"]},
        )

    assert exc_info.value.status_code == 422
    assert "RNA report endpoint" in str(exc_info.value.details)


def test_dna_report_contract_failure_is_returned_as_validation_error(monkeypatch):
    class FailingDnaWorkflow:
        @staticmethod
        def build_report_payload(**_kwargs):
            raise ValueError("No clinical rule source exists for ASP 'assay_1'")

    monkeypatch.setattr(reports, "get_dna_workflow_service", FailingDnaWorkflow)

    with pytest.raises(AppError) as exc_info:
        reports._build_preview_report(
            "dna",
            {"name": "demo_dna_sample"},
            {"asp_id": "assay_1"},
            save=False,
            include_snapshot=True,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.message == "DNA report data does not satisfy the reporting contract"
    assert "No clinical rule source" in str(exc_info.value.details)


def test_preview_report_success_includes_snapshot_when_requested(monkeypatch):
    """Test preview report success includes snapshot when requested.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "asp_id": "WGS", "environment": "prod"},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_preview_report",
        lambda analyte, sample, assay_config, save, include_snapshot: (
            "dna_report.html",
            {"foo": "bar"},
            [{"var": "v1"}],
        ),
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(reports, "render_report_html", lambda **kwargs: "<html>preview</html>")

    payload = reports.preview_report(
        sample_id="S1",
        report_type="dna",
        include_snapshot=True,
        save=False,
        user=_user(role="user"),
    )

    assert payload["sample"]["id"] == "s1"
    assert payload["meta"]["snapshot_count"] == 1
    assert payload["report"]["template"] == "dna_report.html"
    assert payload["report"]["html"] == "<html>preview</html>"
    assert payload["report"]["snapshot_rows"] == [{"var": "v1"}]


def test_preview_report_hides_snapshot_when_not_requested(monkeypatch):
    """Test preview report hides snapshot when not requested.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "asp_id": "WGS", "environment": "prod"},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_preview_report",
        lambda analyte, sample, assay_config, save, include_snapshot: (
            "dna_report.html",
            {"foo": "bar"},
            [{"var": "v1"}],
        ),
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(reports, "render_report_html", lambda **kwargs: "<html>preview</html>")

    payload = reports.preview_report(
        sample_id="S1",
        report_type="dna",
        include_snapshot=False,
        save=False,
        user=_user(role="user"),
    )

    assert payload["meta"]["snapshot_count"] == 1
    assert payload["report"]["snapshot_rows"] == []


def test_save_report_success(monkeypatch):
    """Test save report success.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "asp_id": "WGS", "environment": "prod", "report_num": 2},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_report_location",
        lambda analyte, sample, assay_config: ("RID3", "/tmp", "/tmp/RID3.html"),
    )
    monkeypatch.setattr(
        reports, "_prepare_report_output", lambda analyte, report_path, report_file: None
    )
    monkeypatch.setattr(reports, "_next_report_num", lambda analyte, sample: 3)
    monkeypatch.setattr(
        reports,
        "_build_preview_report",
        lambda analyte, sample, assay_config, save, include_snapshot: (
            "dna_report.html",
            {"sample": sample, "assay_config": {}, "report_sections_data": {}},
            [{"v": 1}],
        ),
    )
    monkeypatch.setattr(reports, "render_report_html", lambda **kwargs: "<html>ready</html>")
    monkeypatch.setattr(
        reports, "_persist_report", lambda analyte, **kwargs: ("oid-123", "/tmp/RID3.pdf")
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_report(
        sample_id="S1",
        report_type="dna",
        user=_user(role="admin"),
    )

    assert payload["report"]["id"] == "RID3"
    assert payload["report"]["oid"] == "oid-123"
    assert payload["report"]["pdf_file"] == "/tmp/RID3.pdf"
    assert payload["report"]["snapshot_count"] == 1
    assert payload["meta"]["status"] == "saved"


def test_save_report_calls_rna_persist_path(monkeypatch):
    """Test save report calls rna persist path.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls: dict[str, str] = {}

    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "asp_id": "RNA", "environment": "prod", "report_num": 5},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_report_location",
        lambda analyte, sample, assay_config: ("RID6", "/tmp", "/tmp/RID6.html"),
    )
    monkeypatch.setattr(
        reports, "_prepare_report_output", lambda analyte, report_path, report_file: None
    )
    monkeypatch.setattr(reports, "_next_report_num", lambda analyte, sample: 6)
    monkeypatch.setattr(
        reports,
        "_build_preview_report",
        lambda analyte, sample, assay_config, save, include_snapshot: (
            "report_fusion.html",
            {"sample": sample, "assay_config": {}, "report_sections_data": {}},
            [],
        ),
    )
    monkeypatch.setattr(reports, "render_report_html", lambda **kwargs: "<html>rna</html>")

    def _persist(analyte, **kwargs):
        """Persist.

        Args:
                analyte: Analyte.
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  persist result.
        """
        calls["analyte"] = analyte
        calls["report_id"] = kwargs["report_id"]
        return "oid-rna", "/tmp/RID6.pdf"

    monkeypatch.setattr(reports, "_persist_report", _persist)
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_report(
        sample_id="S1",
        report_type="rna",
        user=_user(role="admin"),
    )

    assert calls["analyte"] == "rna"
    assert calls["report_id"] == "RID6"
    assert payload["report"]["oid"] == "oid-rna"
    assert payload["report"]["pdf_file"] == "/tmp/RID6.pdf"


def test_restful_report_routes_are_registered():
    """Test restful report routes are registered.

    Returns:
        The function result.
    """
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/samples/{sample_id}/reports/{report_type}/preview" in paths
    assert "/api/v1/samples/{sample_id}/reports/{report_type}/preview/pdf" in paths
    assert "/api/v1/samples/{sample_id}/reports/{report_type}" in paths
