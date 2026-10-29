"""Tests for strict workflow contract validation."""

from __future__ import annotations

import pytest

from coyote3.domain.exceptions import AppError
from coyote3.domain.validation.contracts import (
    validate_report_inputs,
    validate_rna_filter_inputs,
)


class _LoggerStub:
    """Provide  LoggerStub behavior."""

    def error(self, msg: str, *args) -> None:
        """Error."""
        self.last_error = msg % args if args else msg


def test_validate_report_inputs_accepts_valid_payload():
    logger = _LoggerStub()
    validate_report_inputs(
        logger,
        sample={
            "name": "S1",
            "asp_id": "WGS",
            "case_id": "C1",
            "case": {"clarity_id": "CL1"},
        },
        assay_config={
            "asp_group": "dna",
            "reporting": {
                "report_header": "DNA report",
                "report_method": "Panel sequencing",
                "report_folder": "templates/dna_report.html",
            },
        },
        analyte="dna",
    )


def test_validate_report_inputs_raises_on_missing_report_folder():
    logger = _LoggerStub()
    with pytest.raises(AppError) as exc:
        validate_report_inputs(
            logger,
            sample={
                "name": "S1",
                "asp_id": "WGS",
                "case_id": "C1",
                "case": {"clarity_id": "CL1"},
            },
            assay_config={
                "asp_group": "dna",
                "reporting": {
                    "report_header": "DNA report",
                    "report_method": "Panel sequencing",
                },
            },
            analyte="dna",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing assay_config.reporting.report_folder"


def test_validate_report_inputs_raises_on_missing_assay():
    logger = _LoggerStub()
    with pytest.raises(AppError) as exc:
        validate_report_inputs(
            logger,
            sample={"name": "S1", "case_id": "C1", "case": {"clarity_id": "CL1"}},
            assay_config={
                "asp_group": "dna",
                "reporting": {"report_folder": "templates/dna_report.html"},
            },
            analyte="dna",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing sample.asp_id"


def test_validate_rna_filter_inputs_raises_on_non_list_field():
    logger = _LoggerStub()
    with pytest.raises(AppError) as exc:
        validate_rna_filter_inputs(
            logger,
            sample_name="S1",
            sample_filters={"fusion_effects": "in-frame"},
        )
    assert exc.value.status_code == 400
    assert "fusion_effects must be a list" in exc.value.detail["error"]


def test_validate_rna_filter_inputs_raises_on_non_integer_threshold():
    logger = _LoggerStub()
    with pytest.raises(AppError) as exc:
        validate_rna_filter_inputs(
            logger,
            sample_name="S1",
            sample_filters={"min_spanning_reads": "abc"},
        )
    assert exc.value.status_code == 400
    assert "min_spanning_reads must be an integer" in exc.value.detail["error"]
