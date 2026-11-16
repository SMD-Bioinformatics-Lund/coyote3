"""Unit tests for admin workflow services."""

from __future__ import annotations

import pytest
from coyote.application.resources.aspc import AspcService
from coyote.domain.exceptions import AppError


def test_admin_aspc_analysis_types_follow_the_asp_sequencing_family():
    """Targeted RNA panels reject WTS-only capabilities while WTS accepts them."""
    with pytest.raises(AppError) as exc_info:
        AspcService._validate_analysis_types_for_panel(
            {"analysis_types": ["FUSION", "EXPRESSION"]},
            {"asp_family": "panel-rna"},
        )

    assert exc_info.value.status_code == 400
    assert "EXPRESSION" in exc_info.value.message

    AspcService._validate_analysis_types_for_panel(
        {"analysis_types": ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC"]},
        {
            "asp_family": "wts",
            "asp_category": "rna",
            "expected_files": ["fusion_files", "expression_path", "classification_path", "qc"],
        },
    )

    assert AspcService._analysis_types_for_panel(
        {"asp_family": "panel-rna", "expected_files": ["fusion_files", "qc"]}, category="RNA"
    ) == [
        "FUSION",
        "QC",
    ]
    assert "EXPRESSION" in AspcService._analysis_types_for_panel(
        {"asp_family": "wts", "expected_files": ["expression_path"]}, category="RNA"
    )
