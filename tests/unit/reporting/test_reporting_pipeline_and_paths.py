"""Tests for reporting pipeline and path helper services."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from api.application.reporting import persistence as pipeline
from api.domain.core.exceptions import AppError
from api.domain.core.reporting import report_paths
from api.domain.core.reporting.errors import ReportCommitUncertain


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

    monkeypatch.setattr(pipeline, "render_pdf_bytes", lambda _: b"pdf")
    sample_repository = SimpleNamespace(
        save_report=lambda **kwargs: (calls.setdefault("save_report", kwargs), "oid1")[1]
    )
    report_file = str(tmp_path / "seed_report.html")

    report_oid, pdf_file = pipeline.persist_report_and_snapshot(
        sample_id="sample_oid_seed",
        sample={
            "_id": "sample_oid_seed",
            "name": "seed_sample",
            "asp_id": "solid_gmsv3",
            "asp_group": "solid",
            "subpanel_id": "colon",
            "environment": "production",
        },
        report_num=2,
        report_id="seed_report",
        report_file=report_file,
        html="<html/>",
        snapshot_rows=None,
        created_by="tester",
        sample_repository=sample_repository,
    )

    assert report_oid == "oid1"
    assert pdf_file == str(tmp_path / "seed_report.pdf")
    assert Path(report_file).read_text() == "<html/>"
    assert Path(pdf_file).read_bytes() == b"pdf"
    assert calls["save_report"]["sample_id"] == "sample_oid_seed"
    assert calls["save_report"]["snapshot_rows"] == []


def test_persist_report_and_snapshot_raises_when_report_write_fails(monkeypatch, tmp_path):
    """Test persist report and snapshot raises when report write fails.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(pipeline, "render_pdf_bytes", lambda _: b"pdf")

    with pytest.raises(AppError) as exc:
        pipeline.persist_report_and_snapshot(
            sample_id="sample_oid_seed",
            sample={"_id": "sample_oid_seed", "name": "seed_sample"},
            report_num=2,
            report_id="seed_report",
            report_file=str(tmp_path / "missing" / "rid1.html"),
            html="<html/>",
            snapshot_rows=[],
            created_by="tester",
            sample_repository=SimpleNamespace(),
        )

    assert exc.value.status_code == 500
    assert "failed to save report" in exc.value.message.lower()


@pytest.mark.parametrize(
    "folder", ["../outside", "/outside", "nested/../../outside", "..\\outside"]
)
def test_report_folder_cannot_escape_configured_root(tmp_path, folder):
    with pytest.raises(AppError):
        report_paths.build_report_file_location(
            sample={"case_id": "synthetic"},
            assay_config={"reporting": {"report_folder": folder}},
            default_assay_group="test",
            reports_base_path=str(tmp_path),
        )


def test_report_identifier_cannot_inject_path(tmp_path):
    with pytest.raises(AppError):
        report_paths.build_report_file_location(
            sample={"case_id": "../outside"},
            assay_config={"reporting": {"report_folder": "reports"}},
            default_assay_group="test",
            reports_base_path=str(tmp_path),
        )


def test_database_failure_cleans_up_only_new_report_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "render_pdf_bytes", lambda _: b"pdf")

    def fail(**kwargs):
        raise RuntimeError("Synthetic database failure")

    with pytest.raises(AppError):
        pipeline.persist_report_and_snapshot(
            sample_id="synthetic",
            sample={},
            report_num=1,
            report_id="r1",
            report_file=str(tmp_path / "r1.html"),
            html="report",
            snapshot_rows=[],
            created_by="test",
            sample_repository=SimpleNamespace(save_report=fail),
        )
    assert list(tmp_path.iterdir()) == []


def test_exclusive_creation_does_not_overwrite_or_delete_existing_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "render_pdf_bytes", lambda _: b"pdf")
    existing = tmp_path / "r1.pdf"
    existing.write_bytes(b"existing")
    with pytest.raises(AppError) as error:
        pipeline.persist_report_and_snapshot(
            sample_id="synthetic",
            sample={},
            report_num=1,
            report_id="r1",
            report_file=str(tmp_path / "r1.html"),
            html="report",
            snapshot_rows=[],
            created_by="test",
            sample_repository=SimpleNamespace(),
        )
    assert error.value.status_code == 409
    assert existing.read_bytes() == b"existing"
    assert not (tmp_path / "r1.html").exists()


def test_uncertain_commit_retains_artifacts_for_reconciliation(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "render_pdf_bytes", lambda _: b"pdf")

    def uncertain(**kwargs):
        raise ReportCommitUncertain()

    with pytest.raises(ReportCommitUncertain):
        pipeline.persist_report_and_snapshot(
            sample_id="synthetic",
            sample={},
            report_num=1,
            report_id="r1",
            report_file=str(tmp_path / "r1.html"),
            html="report",
            snapshot_rows=[],
            created_by="test",
            sample_repository=SimpleNamespace(save_report=uncertain),
        )
    assert (tmp_path / "r1.html").read_text() == "report"
    assert (tmp_path / "r1.pdf").read_bytes() == b"pdf"
