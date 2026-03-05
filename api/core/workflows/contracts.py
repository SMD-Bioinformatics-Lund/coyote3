
"""Strict workflow input contracts shared by DNA/RNA services."""

from typing import Protocol

from fastapi import HTTPException


class _LoggerLike(Protocol):
    def error(self, msg: str) -> None: ...


def _raise_contract_error(logger: _LoggerLike, tag: str, sample_name: str, message: str) -> None:
    logger.error(f"[contract:{tag}] sample={sample_name} {message}")
    raise HTTPException(status_code=400, detail={"status": 400, "error": message})


def validate_report_inputs(
    logger: _LoggerLike,
    sample: dict | None,
    assay_config: dict | None,
    analyte: str,
) -> None:
    """Validate report-input prerequisites and raise 400 on contract violations."""
    sample = sample or {}
    assay_config = assay_config or {}
    sample_name = str(sample.get("name", "unknown_sample"))

    if not sample.get("assay"):
        _raise_contract_error(logger, "report", sample_name, "Missing sample.assay")
    if not sample.get("case_id"):
        _raise_contract_error(logger, "report", sample_name, "Missing sample.case_id")
    if not sample.get("case", {}).get("clarity_id"):
        _raise_contract_error(logger, "report", sample_name, "Missing sample.case.clarity_id")
    if not assay_config.get("asp_group"):
        _raise_contract_error(logger, "report", sample_name, "Missing assay_config.asp_group")
    reporting = assay_config.get("reporting", {}) or {}
    report_subdir = reporting.get("report_path") or reporting.get("report_folder")
    if not report_subdir:
        _raise_contract_error(
            logger,
            "report",
            sample_name,
            "Missing assay_config.reporting.report_path (or legacy report_folder)",
        )
    if analyte not in {"dna", "rna"}:
        _raise_contract_error(logger, "report", sample_name, f"Invalid analyte value: {analyte}")


def validate_rna_filter_inputs(
    logger: _LoggerLike,
    sample_name: str,
    sample_filters: dict | None,
) -> None:
    """Validate RNA filter payload shape and raise 400 on invalid values."""
    sample_filters = sample_filters or {}
    sample_name = str(sample_name or "unknown_sample")

    for list_key in ("fusion_effects", "fusion_callers", "fusionlists"):
        value = sample_filters.get(list_key)
        if value is not None and not isinstance(value, list):
            _raise_contract_error(
                logger,
                "rna-filters",
                sample_name,
                f"{list_key} must be a list, got {type(value).__name__}",
            )

    for int_key in ("min_spanning_reads", "min_spanning_pairs"):
        value = sample_filters.get(int_key)
        if value is None:
            continue
        try:
            int(value)
        except (TypeError, ValueError):
            _raise_contract_error(
                logger,
                "rna-filters",
                sample_name,
                f"{int_key} must be an integer, got {value}",
            )
