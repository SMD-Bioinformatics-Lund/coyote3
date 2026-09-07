"""Common reporting persistence pipeline for DNA/RNA save flows."""

from __future__ import annotations

import os
from pathlib import Path

from api.application.reporting.report_renderer import render_pdf_bytes
from api.domain.core.exceptions import AppError
from api.domain.core.reporting.errors import ReportCommitUncertain


def prepare_report_output(report_path: str, report_file: str, logger=None) -> None:
    """
    Ensure report output directory exists and target file is not already present.
    """
    os.makedirs(report_path, exist_ok=True)
    if os.path.exists(report_file):
        if logger is not None:
            logger.warning("Report file already exists: %s", report_file)
        raise AppError(
            status_code=409,
            message="Report already exists with the requested name.",
            details=f"File name: {os.path.basename(report_file)}",
        )
    pdf_file = os.path.splitext(report_file)[0] + ".pdf"
    if os.path.exists(pdf_file):
        if logger is not None:
            logger.warning("Report PDF already exists: %s", pdf_file)
        raise AppError(
            status_code=409,
            message="Report PDF already exists with the requested name.",
            details=f"File name: {os.path.basename(pdf_file)}",
        )


def persist_report_and_snapshot(
    *,
    sample_id: str,
    sample: dict,
    report_num: int,
    report_id: str,
    report_file: str,
    html: str,
    snapshot_rows: list | None,
    created_by: str,
    sample_repository,
    rule_provenance: dict | None = None,
) -> tuple[str, str]:
    """
    Persist report HTML, report metadata, and typed report-finding snapshot rows.
    Returns created report_oid and PDF file path.
    """
    pdf_file = os.path.splitext(report_file)[0] + ".pdf"
    created: list[Path] = []
    try:
        pdf_bytes = render_pdf_bytes(html)
        for path, content in (
            (Path(report_file), html.encode("utf-8")),
            (Path(pdf_file), pdf_bytes),
        ):
            with path.open("xb") as handle:
                created.append(path)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        report_oid = sample_repository.save_report(
            sample_id=sample_id,
            report_num=report_num,
            report_id=report_id,
            filepath=report_file,
            pdf_filepath=pdf_file,
            rule_provenance=rule_provenance,
            snapshot_rows=snapshot_rows or [],
            created_by=created_by,
        )
        if report_oid is None:
            raise AppError(404, "Sample no longer exists.")
    except ReportCommitUncertain:
        # A committed report must never lose its artifacts after an ambiguous acknowledgement.
        raise
    except Exception as exc:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if isinstance(exc, AppError):
            raise
        if isinstance(exc, FileExistsError):
            raise AppError(409, "Report artifact already exists.") from exc
        raise AppError(500, "Failed to save report.") from exc
    return report_oid, pdf_file
