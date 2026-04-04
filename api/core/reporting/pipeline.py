"""
Shared reporting persistence pipeline for DNA/RNA save flows.
"""

from __future__ import annotations

import os

from api.core.exceptions import AppError
from api.core.reporting.ports import ReportingPersistenceRepository
from api.extensions import store, util


def _reporting_repository() -> ReportingPersistenceRepository:
    """Return the active reporting persistence repository."""
    return store.get_reporting_persistence_repository()


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
) -> str:
    """
    Persist report HTML + report metadata + reported-variants snapshot rows.
    Returns created report_oid.
    """
    if not util.common.write_report(html, report_file):
        raise AppError(
            status_code=500,
            message=f"Failed to save report {report_id}.html",
            details="Could not write the report to the file system.",
        )

    report_oid = _reporting_repository().save_report(
        sample_id=sample_id,
        report_num=report_num,
        report_id=report_id,
        filepath=report_file,
    )

    _reporting_repository().bulk_upsert_snapshot_rows(
        sample_name=sample.get("name"),
        sample_oid=sample.get("_id"),
        report_oid=report_oid,
        report_id=report_id,
        snapshot_rows=snapshot_rows or [],
        created_by=created_by,
    )
    return report_oid
