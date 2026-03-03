"""Behavior tests for report API routes (preview/save)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.app import ApiUser
from api.routes import reports


def _user(username: str = "tester", role: str = "admin") -> ApiUser:
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username=username,
        role=role,
        access_level=99,
        permissions=["preview_report", "create_report"],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna", "rna"],
        envs=["dev"],
        asp_map={},
    )


def test_normalize_rendered_report_payload_success():
    html, rows = reports._normalize_rendered_report_payload(
        {"html": "<html>ok</html>", "snapshot_rows": [{"id": 1}]}
    )
    assert html == "<html>ok</html>"
    assert rows == [{"id": 1}]


def test_normalize_rendered_report_payload_missing_html_raises_400():
    with pytest.raises(HTTPException) as exc:
        reports._normalize_rendered_report_payload({"snapshot_rows": []})
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing rendered report html"


def test_normalize_rendered_report_payload_invalid_snapshot_rows_raises_400():
    with pytest.raises(HTTPException) as exc:
        reports._normalize_rendered_report_payload({"html": "<html>x</html>", "snapshot_rows": {}})
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid snapshot_rows payload"


def test_preview_dna_report_success_includes_snapshot_when_requested(monkeypatch):
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: ({"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod"}, {"x": 1}),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None)
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

    payload = reports.preview_dna_report(
        sample_id="S1",
        include_snapshot=True,
        save=False,
        user=_user(role="user"),
    )

    assert payload["sample"]["id"] == "s1"
    assert payload["meta"]["snapshot_count"] == 1
    assert payload["report"]["template"] == "dna_report.html"
    assert payload["report"]["snapshot_rows"] == [{"var": "v1"}]


def test_preview_dna_report_hides_snapshot_when_not_requested(monkeypatch):
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: ({"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod"}, {"x": 1}),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None)
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

    payload = reports.preview_dna_report(
        sample_id="S1",
        include_snapshot=False,
        save=False,
        user=_user(role="user"),
    )

    assert payload["meta"]["snapshot_count"] == 1
    assert payload["report"]["snapshot_rows"] == []


def test_save_dna_report_success(monkeypatch):
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod", "report_num": 2},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None)
    monkeypatch.setattr(reports, "_build_report_location", lambda analyte, sample, assay_config: ("RID3", "/tmp", "RID3.pdf"))
    monkeypatch.setattr(reports, "_prepare_report_output", lambda analyte, report_path, report_file: None)
    monkeypatch.setattr(
        reports,
        "_persist_report",
        lambda analyte, **kwargs: "oid-123",
    )
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_dna_report(
        sample_id="S1",
        report_payload={"html": "<html>ready</html>", "snapshot_rows": [{"v": 1}]},
        user=_user(role="admin"),
    )

    assert payload["report"]["id"] == "RID3"
    assert payload["report"]["oid"] == "oid-123"
    assert payload["report"]["snapshot_count"] == 1
    assert payload["meta"]["status"] == "saved"


def test_save_dna_report_missing_html_raises_400(monkeypatch):
    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "assay": "WGS", "profile": "prod", "report_num": 2},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None)
    monkeypatch.setattr(reports, "_build_report_location", lambda analyte, sample, assay_config: ("RID3", "/tmp", "RID3.pdf"))
    monkeypatch.setattr(reports, "_prepare_report_output", lambda analyte, report_path, report_file: None)

    with pytest.raises(HTTPException) as exc:
        reports.save_dna_report(
            sample_id="S1",
            report_payload={"snapshot_rows": []},
            user=_user(role="admin"),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing rendered report html"


def test_save_rna_report_calls_rna_persist_path(monkeypatch):
    calls: dict[str, str] = {}

    monkeypatch.setattr(
        reports,
        "_load_report_context",
        lambda sample_id, user: (
            {"_id": "s1", "name": "S1", "assay": "RNA", "profile": "prod", "report_num": 5},
            {"x": 1},
        ),
    )
    monkeypatch.setattr(reports, "_validate_report_inputs", lambda analyte, sample, assay_config: None)
    monkeypatch.setattr(reports, "_build_report_location", lambda analyte, sample, assay_config: ("RID6", "/tmp", "RID6.pdf"))
    monkeypatch.setattr(reports, "_prepare_report_output", lambda analyte, report_path, report_file: None)

    def _persist(analyte, **kwargs):
        calls["analyte"] = analyte
        calls["report_id"] = kwargs["report_id"]
        return "oid-rna"

    monkeypatch.setattr(reports, "_persist_report", _persist)
    monkeypatch.setattr(reports.util.common, "convert_to_serializable", lambda payload: payload)

    payload = reports.save_rna_report(
        sample_id="S1",
        report_payload={"html": "<html>rna</html>", "snapshot_rows": []},
        user=_user(role="admin"),
    )

    assert calls["analyte"] == "rna"
    assert calls["report_id"] == "RID6"
    assert payload["report"]["oid"] == "oid-rna"
