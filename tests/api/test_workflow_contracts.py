"""Tests for strict workflow contract validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.core.workflows.contracts import validate_report_inputs, validate_rna_filter_inputs


class _LoggerStub:
    def error(self, msg: str) -> None:
        self.last_error = msg


def test_validate_report_inputs_accepts_valid_payload():
    logger = _LoggerStub()
    validate_report_inputs(
        logger,
        sample={
            "name": "S1",
            "assay": "WGS",
            "case_id": "C1",
            "case": {"clarity_id": "CL1"},
        },
        assay_config={"asp_group": "dna", "reporting": {"report_path": "templates/dna_report.html"}},
        analyte="dna",
    )


def test_validate_report_inputs_raises_on_missing_assay():
    logger = _LoggerStub()
    with pytest.raises(HTTPException) as exc:
        validate_report_inputs(
            logger,
            sample={"name": "S1", "case_id": "C1", "case": {"clarity_id": "CL1"}},
            assay_config={"asp_group": "dna", "reporting": {"report_path": "templates/dna_report.html"}},
            analyte="dna",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Missing sample.assay"


def test_validate_rna_filter_inputs_raises_on_non_list_field():
    logger = _LoggerStub()
    with pytest.raises(HTTPException) as exc:
        validate_rna_filter_inputs(
            logger,
            sample_name="S1",
            sample_filters={"fusion_effects": "in-frame"},
        )
    assert exc.value.status_code == 400
    assert "fusion_effects must be a list" in exc.value.detail["error"]


def test_validate_rna_filter_inputs_raises_on_non_integer_threshold():
    logger = _LoggerStub()
    with pytest.raises(HTTPException) as exc:
        validate_rna_filter_inputs(
            logger,
            sample_name="S1",
            sample_filters={"min_spanning_reads": "abc"},
        )
    assert exc.value.status_code == 400
    assert "min_spanning_reads must be an integer" in exc.value.detail["error"]
