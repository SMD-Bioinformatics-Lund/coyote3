"""Validate report output locations against the configured mounted root."""

import os
from pathlib import Path
from typing import Any, Tuple

from coyote3.domain.exceptions import AppError
from coyote3.domain.reporting.report_paths import get_report_timestamp


def build_report_file_location(
    *,
    sample: dict[str, Any],
    assay_config: dict[str, Any],
    default_assay_group: str,
    reports_base_path: str,
) -> Tuple[str, str, str]:
    """Build the report identity and validated file location for DNA and RNA saves.

    Args:
        sample: Sample identifiers and optional case/control records; null records
            contribute no clarity identifier.
        assay_config: Published configuration containing reporting.report_folder.
        default_assay_group: Assay group used in missing-configuration diagnostics.
        reports_base_path: Root directory within which report files must remain.

    Returns:
        Report identifier, absolute parent directory and HTML file path.

    Raises:
        AppError: Report identifiers or configured folders contain unsafe paths,
            or the report folder is missing.
    """
    case_id = sample.get("case_id")
    control_id = sample.get("control_id")
    clarity_case_id = (sample.get("case") or {}).get("clarity_id")
    clarity_control_id = (sample.get("control") or {}).get("clarity_id")
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
