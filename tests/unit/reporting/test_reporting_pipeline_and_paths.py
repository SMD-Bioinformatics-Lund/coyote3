"""Tests for reporting pipeline and path helper services."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.core.reporting import pipeline, report_paths
from api.errors.exceptions import AppError


def test_build_report_file_location_with_control_id(monkeypatch):
    monkeypatch.setattr(report_paths, "get_report_timestamp", lambda: "260303101112")
    sample = {
        "case_id": "CASE1",
        "control_id": "CTRL1",
        "case": {"clarity_id": "CC1"},
        "control": {"clarity_id": "CT1"},
    }
    assay_config = {"reporting": {"report_path": "dna/reports"}}

    report_id, report_path, report_file = report_paths.build_report_file_location(
        sample=sample,
        assay_config=assay_config,
        default_assay_group="dna",
        reports_base_path="/reports",
    )

    assert report_id == "CASE1_CC1-CTRL1_CT1.260303101112"
    assert report_path == "/reports/dna/reports"
    assert report_file == "/reports/dna/reports/CASE1_CC1-CTRL1_CT1.260303101112.html"


def test_build_report_file_location_without_control_id_uses_case_only(monkeypatch):
    monkeypatch.setattr(report_paths, "get_report_timestamp", lambda: "260303101112")
    sample = {
        "case_id": "CASE1",
        "case": {"clarity_id": "CC1"},
    }

    report_id, report_path, report_file = report_paths.build_report_file_location(
        sample=sample,
        assay_config={},
        default_assay_group="rna",
        reports_base_path="/reports",
    )

    assert report_id == "CASE1_CC1.260303101112"
    assert report_path == "/reports/rna"
    assert report_file == "/reports/rna/CASE1_CC1.260303101112.html"


def test_prepare_report_output_creates_directory_when_file_missing(monkeypatch):
    calls = {"makedirs": []}

    monkeypatch.setattr(
        pipeline.os,
        "makedirs",
        lambda path, exist_ok: calls["makedirs"].append((path, exist_ok)),
    )
    monkeypatch.setattr(pipeline.os.path, "exists", lambda _path: False)

    pipeline.prepare_report_output("/reports/dna", "/reports/dna/r1.html")

    assert calls["makedirs"] == [("/reports/dna", True)]


def test_prepare_report_output_raises_conflict_when_file_exists(monkeypatch):
    class _Logger:
        def __init__(self):
            self.messages = []

        def warning(self, msg):
            self.messages.append(msg)

    logger = _Logger()
    monkeypatch.setattr(pipeline.os, "makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline.os.path, "exists", lambda _path: True)

    with pytest.raises(AppError) as exc:
        pipeline.prepare_report_output("/reports/dna", "/reports/dna/r1.html", logger=logger)

    assert exc.value.status_code == 409
    assert "already exists" in exc.value.message.lower()
    assert logger.messages


def test_persist_report_and_snapshot_writes_report_and_upserts_snapshot(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        pipeline,
        "util",
        SimpleNamespace(
            common=SimpleNamespace(
                write_report=lambda html, path: calls.setdefault("write", (html, path)) and True
            )
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "store",
        SimpleNamespace(
            sample_handler=SimpleNamespace(
                save_report=lambda **kwargs: (calls.setdefault("save_report", kwargs), "oid1")[1]
            ),
            reported_variants_handler=SimpleNamespace(
                bulk_upsert_from_snapshot_rows=lambda **kwargs: calls.setdefault(
                    "bulk_upsert", kwargs
                )
            ),
        ),
    )

    report_oid = pipeline.persist_report_and_snapshot(
        sample_id="s1",
        sample={"_id": "s1", "name": "SAMPLE1"},
        report_num=2,
        report_id="RID1",
        report_file="/reports/rid1.html",
        html="<html/>",
        snapshot_rows=None,
        created_by="tester",
    )

    assert report_oid == "oid1"
    assert calls["write"] == ("<html/>", "/reports/rid1.html")
    assert calls["save_report"]["sample_id"] == "s1"
    assert calls["bulk_upsert"]["snapshot_rows"] == []


def test_persist_report_and_snapshot_raises_when_report_write_fails(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "util",
        SimpleNamespace(common=SimpleNamespace(write_report=lambda _html, _path: False)),
    )

    with pytest.raises(AppError) as exc:
        pipeline.persist_report_and_snapshot(
            sample_id="s1",
            sample={"_id": "s1", "name": "SAMPLE1"},
            report_num=2,
            report_id="RID1",
            report_file="/reports/rid1.html",
            html="<html/>",
            snapshot_rows=[],
            created_by="tester",
        )

    assert exc.value.status_code == 500
    assert "failed to save report" in exc.value.message.lower()
