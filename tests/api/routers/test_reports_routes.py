"""Behavior tests for report API routes (preview/save)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.main import app as api_app
from api.routers import reports
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
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna", "rna"],
        envs=["dev"],
        asp_map={},
    )


def test_normalize_rendered_report_payload_success():
    """Test normalize rendered report payload success.

    Returns:
        The function result.
    """
    html, rows = reports._normalize_rendered_report_payload(
        {"html": "<html>ok</html>", "snapshot_rows": [{"id": 1}]}
    )
    assert html == "<html>ok</html>"
    assert rows == [{"id": 1}]


def test_normalize_rendered_report_payload_missing_html_raises_400():
    """Test normalize rendered report payload missing html raises 400.

    Returns:
        The function result.
    """
    with pytest.raises(HTTPException) as exc:
        reports._normalize_rendered_report_payload({"snapshot_rows": []})
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing rendered report html"


def test_normalize_rendered_report_payload_invalid_snapshot_rows_raises_400():
    """Test normalize rendered report payload invalid snapshot rows raises 400.

    Returns:
        The function result.
    """
    with pytest.raises(HTTPException) as exc:
        reports._normalize_rendered_report_payload({"html": "<html>x</html>", "snapshot_rows": {}})
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid snapshot_rows payload"


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
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod"},
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
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod"},
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
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod", "report_num": 2},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_report_location",
        lambda analyte, sample, assay_config: ("RID3", "/tmp", "RID3.pdf"),
    )
    monkeypatch.setattr(
        reports, "_prepare_report_output", lambda analyte, report_path, report_file: None
    )
    monkeypatch.setattr(
        reports,
        "_persist_report",
        lambda analyte, **kwargs: "oid-123",
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_report(
        sample_id="S1",
        report_type="dna",
        report_payload={"html": "<html>ready</html>", "snapshot_rows": [{"v": 1}]},
        user=_user(role="admin"),
    )

    assert payload["report"]["id"] == "RID3"
    assert payload["report"]["oid"] == "oid-123"
    assert payload["report"]["snapshot_count"] == 1
    assert payload["meta"]["status"] == "saved"


def test_save_dna_report_missing_html_raises_400(monkeypatch):
    """Test save dna report missing html raises 400.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod", "report_num": 2},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_report_location",
        lambda analyte, sample, assay_config: ("RID3", "/tmp", "RID3.pdf"),
    )
    monkeypatch.setattr(
        reports, "_prepare_report_output", lambda analyte, report_path, report_file: None
    )

    with pytest.raises(HTTPException) as exc:
        reports.save_report(
            sample_id="S1",
            report_type="dna",
            report_payload={"snapshot_rows": []},
            user=_user(role="admin"),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing rendered report html"


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
            {"_id": "s1", "name": "S1", "assay": "RNA", "profile": "prod", "report_num": 5},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(
        reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None
    )
    monkeypatch.setattr(
        reports,
        "_build_report_location",
        lambda analyte, sample, assay_config: ("RID6", "/tmp", "RID6.pdf"),
    )
    monkeypatch.setattr(
        reports, "_prepare_report_output", lambda analyte, report_path, report_file: None
    )

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
        return "oid-rna"

    monkeypatch.setattr(reports, "_persist_report", _persist)
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_report(
        sample_id="S1",
        report_type="rna",
        report_payload={"html": "<html>rna</html>", "snapshot_rows": []},
        user=_user(role="admin"),
    )

    assert calls["analyte"] == "rna"
    assert calls["report_id"] == "RID6"
    assert payload["report"]["oid"] == "oid-rna"


def test_restful_report_routes_are_registered():
    """Test restful report routes are registered.

    Returns:
        The function result.
    """
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/samples/{sample_id}/reports/{report_type}/preview" in paths
    assert "/api/v1/samples/{sample_id}/reports/{report_type}" in paths
