"""Report path/id generation helpers."""

import os
from pathlib import Path
from typing import Tuple
from uuid import uuid4

from api.domain.common.reporting import utc_now
from api.domain.core.exceptions import AppError


def get_report_timestamp() -> str:
    """Return UTC timestamp suffix used in report ids."""
    return f"{utc_now():%y%m%d%H%M%S}-{uuid4().hex}"


def build_report_file_location(
    *,
    sample: dict,
    assay_config: dict,
    default_assay_group: str,
    reports_base_path: str,
) -> Tuple[str, str, str]:
    """Build report id/path/file location used by both DNA and RNA save flows."""
    case_id = sample.get("case_id")
    control_id = sample.get("control_id")
    clarity_case_id = sample.get("case", {}).get("clarity_id")
    clarity_control_id = sample.get("control", {}).get("clarity_id")
    report_timestamp = get_report_timestamp()

    if control_id:
        report_id = (
            f"{case_id}_{clarity_case_id}-{control_id}_{clarity_control_id}.{report_timestamp}"
        )
    else:
        report_id = f"{case_id}_{clarity_case_id}.{report_timestamp}"

    if any(character in report_id for character in ("/", "\\", "\x00")):
        raise AppError(400, "Report identifiers cannot contain path separators.")

    reporting = assay_config.get("reporting", {}) or {}
    report_subdir = str(reporting.get("report_folder") or "").strip()
    if not report_subdir:
        raise AppError(
            400,
            (
                f"Missing assay_config.reporting.report_folder for assay group '{default_assay_group}'"
            ),
        )
    base = Path(reports_base_path).resolve()
    relative = Path(report_subdir)
    if relative.is_absolute() or ".." in relative.parts or "\\" in report_subdir:
        raise AppError(400, "Report folder must be a relative path within the reports directory.")
    destination = (base / relative).resolve()
    if not destination.is_relative_to(base):
        raise AppError(400, "Report folder escapes the reports directory.")
    report_path = str(destination)
    report_file = os.path.join(report_path, f"{report_id}.html")
    return report_id, report_path, report_file
