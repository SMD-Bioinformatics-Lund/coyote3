"""Report path/id generation helpers."""

import os
from typing import Tuple

from api.common.utility import utc_now
from api.core.exceptions import AppError


def get_report_timestamp() -> str:
    """Return UTC timestamp suffix used in report ids."""
    return utc_now().strftime("%y%m%d%H%M%S")


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

    reporting = assay_config.get("reporting", {}) or {}
    report_subdir = str(reporting.get("report_path") or "").strip()
    if not report_subdir:
        raise AppError(
            400,
            (
                "Missing assay_config.reporting.report_path "
                f"for assay group '{default_assay_group}'"
            ),
        )
    report_path = os.path.join(reports_base_path, report_subdir)
    report_file = os.path.join(report_path, f"{report_id}.html")
    return report_id, report_path, report_file
