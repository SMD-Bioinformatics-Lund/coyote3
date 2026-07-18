"""Tests for reporting pipeline and path helper services."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.reporting import persistence as pipeline
from api.domain.core.exceptions import AppError
from api.domain.core.reporting import report_paths


def test_build_report_file_location_with_control_id(monkeypatch):
    """Test build report file location with control id.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(report_paths, "get_report_timestamp", lambda: "260303101112")
    sample = {
        "case_id": "seed_case",
        "control_id": "seed_control",
        "case": {"clarity_id": "seed_case_clarity"},
        "control": {"clarity_id": "seed_control_clarity"},
    }
    assay_config = {"reporting": {"report_folder": "dna/reports"}}

    report_id, report_path, report_file = report_paths.build_report_file_location(
        sample=sample,
        assay_config=assay_config,
        default_assay_group="dna",
        reports_base_path="/reports",
    )

    assert report_id == "seed_case_seed_case_clarity-seed_control_seed_control_clarity.260303101112"
    assert report_path == "/reports/dna/reports"
    assert (
        report_file
        == "/reports/dna/reports/seed_case_seed_case_clarity-seed_control_seed_control_clarity.260303101112.html"
    )


def test_build_report_file_location_without_control_id_uses_case_only(monkeypatch):
    """Test build report file location without control id uses case only.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(report_paths, "get_report_timestamp", lambda: "260303101112")
    sample = {
        "case_id": "seed_case",
        "case": {"clarity_id": "seed_case_clarity"},
    }

    report_id, report_path, report_file = report_paths.build_report_file_location(
        sample=sample,
        assay_config={"reporting": {"report_folder": "rna"}},
        default_assay_group="rna",
        reports_base_path="/reports",
    )

    assert report_id == "seed_case_seed_case_clarity.260303101112"
    assert report_path == "/reports/rna"
    assert report_file == "/reports/rna/seed_case_seed_case_clarity.260303101112.html"


def test_build_report_file_location_raises_without_report_path(monkeypatch):
    """Test build report file location raises without report path.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(report_paths, "get_report_timestamp", lambda: "260303101112")
    sample = {"case_id": "seed_case", "case": {"clarity_id": "seed_case_clarity"}}

    with pytest.raises(AppError) as exc:
        report_paths.build_report_file_location(
            sample=sample,
            assay_config={},
            default_assay_group="rna",
            reports_base_path="/reports",
        )

    assert exc.value.status_code == 400
    assert "report_folder" in exc.value.message


def test_prepare_report_output_creates_directory_when_file_missing(monkeypatch):
    """Test prepare report output creates directory when file missing.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
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
    """Test prepare report output raises conflict when file exists.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """

    class _Logger:
        """Provide  Logger behavior."""

        def __init__(self):
            """__init__."""
            self.messages = []

        def warning(self, msg, *args):
            """Warning.

            Args:
                msg: Value for ``msg``.
                args: Value for ``args``.

            Returns:
                The function result.
            """
            self.messages.append(msg % args if args else msg)

    logger = _Logger()
    monkeypatch.setattr(pipeline.os, "makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline.os.path, "exists", lambda _path: True)

    with pytest.raises(AppError) as exc:
        pipeline.prepare_report_output("/reports/dna", "/reports/dna/r1.html", logger=logger)

    assert exc.value.status_code == 409
    assert "already exists" in exc.value.message.lower()
    assert logger.messages


def test_persist_report_and_snapshot_writes_report_and_upserts_snapshot(monkeypatch, tmp_path):
    """Test persist report and snapshot writes report and upserts snapshot.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
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
    sample_repository = SimpleNamespace(
        save_report=lambda **kwargs: (calls.setdefault("save_report", kwargs), "oid1")[1]
    )
    reported_variant_repository = SimpleNamespace(
        bulk_upsert_from_snapshot_rows=lambda **kwargs: calls.setdefault("bulk_upsert", kwargs)
    )
    report_file = str(tmp_path / "seed_report.html")

    report_oid, pdf_file = pipeline.persist_report_and_snapshot(
        sample_id="sample_oid_seed",
        sample={"_id": "sample_oid_seed", "name": "seed_sample"},
        report_num=2,
        report_id="seed_report",
        report_file=report_file,
        html="<html/>",
        snapshot_rows=None,
        created_by="tester",
        sample_repository=sample_repository,
        reported_variant_repository=reported_variant_repository,
    )

    assert report_oid == "oid1"
    assert pdf_file == str(tmp_path / "seed_report.pdf")
    assert calls["write"] == ("<html/>", report_file)
    assert calls["save_report"]["sample_id"] == "sample_oid_seed"
    assert calls["bulk_upsert"]["snapshot_rows"] == []


def test_persist_report_and_snapshot_raises_when_report_write_fails(monkeypatch):
    """Test persist report and snapshot raises when report write fails.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        pipeline,
        "util",
        SimpleNamespace(common=SimpleNamespace(write_report=lambda _html, _path: False)),
    )

    with pytest.raises(AppError) as exc:
        pipeline.persist_report_and_snapshot(
            sample_id="sample_oid_seed",
            sample={"_id": "sample_oid_seed", "name": "seed_sample"},
            report_num=2,
            report_id="seed_report",
            report_file="/reports/rid1.html",
            html="<html/>",
            snapshot_rows=[],
            created_by="tester",
            sample_repository=SimpleNamespace(),
            reported_variant_repository=SimpleNamespace(),
        )

    assert exc.value.status_code == 500
    assert "failed to save report" in exc.value.message.lower()
