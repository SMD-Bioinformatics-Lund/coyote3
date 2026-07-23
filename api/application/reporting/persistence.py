"""Common reporting persistence pipeline for DNA/RNA save flows."""

from __future__ import annotations

import os
from types import SimpleNamespace

from api.application.reporting.report_renderer import render_pdf_bytes
from api.domain.common.reporting import write_report
from api.domain.core.exceptions import AppError

util = SimpleNamespace(common=SimpleNamespace(write_report=write_report))


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
    reported_variant_repository,
    rule_provenance: dict | None = None,
) -> tuple[str, str]:
    """
    Persist report HTML + report metadata + reported-variants snapshot rows.
    Returns created report_oid and PDF file path.
    """
    if not util.common.write_report(html, report_file):
        raise AppError(
            status_code=500,
            message=f"Failed to save report {report_id}.html",
            details="Could not write the report to the file system.",
        )
    pdf_file = os.path.splitext(report_file)[0] + ".pdf"
    try:
        pdf_bytes = render_pdf_bytes(html)
        with open(pdf_file, "wb") as handle:
            handle.write(pdf_bytes)
    except Exception as exc:
        raise AppError(
            status_code=500,
            message=f"Failed to save report {report_id}.pdf",
            details=str(exc),
        ) from exc

    report_oid = sample_repository.save_report(
        sample_id=sample_id,
        report_num=report_num,
        report_id=report_id,
        filepath=report_file,
        pdf_filepath=pdf_file,
        rule_provenance=rule_provenance,
    )

    reported_variant_repository.bulk_upsert_from_snapshot_rows(
        sample_name=sample.get("name"),
        sample_oid=sample.get("_id"),
        report_oid=report_oid,
        report_id=report_id,
        report_num=report_num,
        snapshot_rows=snapshot_rows or [],
        created_by=created_by,
    )
    return report_oid, pdf_file
