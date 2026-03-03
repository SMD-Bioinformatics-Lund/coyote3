"""Behavior tests for Coverage API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes import coverage
from tests.api.fixtures import mock_collections as fx


def test_coverage_sample_read_builds_payload(monkeypatch):
    sample = fx.sample_doc()
    sample["filters"] = {"genelists": ["GL1"]}
    sample["assay"] = "WGS"
    sample["profile"] = "production"

    monkeypatch.setattr(coverage, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(
        coverage.store.aspc_handler,
        "get_aspc_no_meta",
        lambda assay, profile: {"assay_group": "dna"},
    )
    monkeypatch.setattr(
        coverage.store.asp_handler,
        "get_asp",
        lambda asp_name: {"_id": "WGS", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        coverage.util.common,
        "get_sample_effective_genes",
        lambda sample, assay_panel_doc, checked_genelists_genes_dict: (["TP53", "NPM1"], ["TP53"]),
    )
    monkeypatch.setattr(coverage.store.isgl_handler, "get_isgl_by_ids", lambda ids: {"GL1": {"genes": ["TP53"]}})
    monkeypatch.setattr(
        coverage.store.coverage2_handler,
        "get_sample_coverage",
        lambda sample_id: {"_id": "cov1", "TP53": {"mean": 700}},
    )
    monkeypatch.setattr(
        coverage.CoverageProcessingService,
        "filter_genes_from_form",
        lambda cov_dict, filter_genes, assay_group: cov_dict,
    )
    monkeypatch.setattr(
        coverage.CoverageProcessingService,
        "find_low_covered_genes",
        lambda filtered_dict, cutoff, assay_group: filtered_dict,
    )
    monkeypatch.setattr(
        coverage.CoverageProcessingService,
        "coverage_table",
        lambda filtered_dict, cutoff: [{"gene": "TP53", "mean": 700}],
    )
    monkeypatch.setattr(
        coverage.CoverageProcessingService,
        "organize_data_for_d3",
        lambda filtered_dict: {"genes": [{"name": "TP53"}]},
    )
    monkeypatch.setattr(coverage.util.common, "convert_to_serializable", lambda payload: payload)

    payload = coverage.coverage_sample_read("S1", cov_cutoff=500, user=fx.api_user())

    assert payload["cov_cutoff"] == 500
    assert payload["smp_grp"] == "dna"
    assert payload["genelists"] == ["GL1"]
    assert payload["cov_table"][0]["gene"] == "TP53"


def test_coverage_blacklisted_read_denies_non_member_group():
    user = fx.api_user()
    user.assay_groups = ["rna"]

    with pytest.raises(HTTPException) as exc:
        coverage.coverage_blacklisted_read("dna", user=user)

    assert exc.value.status_code == 403
    assert "Access denied" in exc.value.detail["error"]
