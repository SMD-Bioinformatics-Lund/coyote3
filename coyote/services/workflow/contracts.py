#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Warn-only workflow contracts for migration safety.

These checks intentionally DO NOT raise or alter behavior.
They only emit warnings for contract drift during phased refactoring.
"""

from typing import Any, Protocol


class _LoggerLike(Protocol):
    def warning(self, msg: str) -> None: ...


def _warn(logger: _LoggerLike, tag: str, sample_name: str, message: str) -> None:
    logger.warning(f"[contract:{tag}] sample={sample_name} {message}")


def validate_report_inputs_warn_only(
    logger: _LoggerLike,
    sample: dict | None,
    assay_config: dict | None,
    analyte: str,
) -> None:
    """
    Validate report-input prerequisites in warn-only mode.
    """
    sample = sample or {}
    assay_config = assay_config or {}
    sample_name = sample.get("name", "unknown_sample")

    if not sample.get("assay"):
        _warn(logger, "report", sample_name, "missing sample.assay")
    if not sample.get("case_id"):
        _warn(logger, "report", sample_name, "missing sample.case_id")
    if not sample.get("case", {}).get("clarity_id"):
        _warn(logger, "report", sample_name, "missing sample.case.clarity_id")
    if not assay_config.get("asp_group"):
        _warn(logger, "report", sample_name, "missing assay_config.asp_group")
    if not assay_config.get("reporting", {}).get("report_path"):
        _warn(logger, "report", sample_name, "missing assay_config.reporting.report_path")
    if analyte not in {"dna", "rna"}:
        _warn(logger, "report", sample_name, f"unexpected analyte value: {analyte}")


def validate_rna_filter_inputs_warn_only(
    logger: _LoggerLike,
    sample_name: str,
    sample_filters: dict | None,
) -> None:
    """
    Validate RNA filter payload shape in warn-only mode.
    """
    sample_filters = sample_filters or {}

    if "min_spanning_reads" not in sample_filters and "spanning_reads" in sample_filters:
        _warn(logger, "rna-filters", sample_name, "using legacy key spanning_reads")
    if "min_spanning_pairs" not in sample_filters and "spanning_pairs" in sample_filters:
        _warn(logger, "rna-filters", sample_name, "using legacy key spanning_pairs")

    for list_key in ("fusion_effects", "fusion_callers", "fusionlists"):
        value = sample_filters.get(list_key)
        if value is not None and not isinstance(value, list):
            _warn(logger, "rna-filters", sample_name, f"{list_key} is {type(value).__name__}, expected list")

    for int_key in ("min_spanning_reads", "min_spanning_pairs"):
        value = sample_filters.get(int_key)
        if value is None:
            continue
        try:
            int(value)
        except (TypeError, ValueError):
            _warn(logger, "rna-filters", sample_name, f"{int_key} is non-integer: {value}")
