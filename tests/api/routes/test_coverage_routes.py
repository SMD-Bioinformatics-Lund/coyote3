"""Behavior tests for Coverage API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import app as api_app
from api.routes import coverage
from api.security import access
from api.security.access import ApiUser
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
        lambda filtered_dict, cutoff: {"TP53": {"1": {"cov": 700}}},
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
    assert payload["cov_table"]["TP53"]["1"]["cov"] == 700


def test_coverage_blacklisted_read_denies_non_member_group():
    user = fx.api_user()
    user.assay_groups = ["rna"]

    with pytest.raises(HTTPException) as exc:
        coverage.coverage_blacklisted_read("dna", user=user)

    assert exc.value.status_code == 403
    assert "Access denied" in exc.value.detail["error"]


def _route_test_user() -> ApiUser:
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="user",
        access_level=9,
        permissions=[],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
    )


def test_coverage_sample_read_http_validates_cov_table_dict_shape(monkeypatch):
    sample = fx.sample_doc()
    sample["filters"] = {"genelists": ["GL1"]}
    sample["assay"] = "WGS"
    sample["profile"] = "production"
    sample["_id"] = "S1"

    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(coverage, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(coverage.store.aspc_handler, "get_aspc_no_meta", lambda assay, profile: {"assay_group": "dna"})
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
        lambda sample_id: {"_id": "cov1", "genes": {"TP53": {"CDS": {"1": {"cov": "700"}}}}},
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
        lambda filtered_dict, cutoff: {"TP53": {"1": {"cov": "700"}}},
    )
    monkeypatch.setattr(
        coverage.CoverageProcessingService,
        "organize_data_for_d3",
        lambda filtered_dict: {"genes": {"TP53": {"CDS": [{"cov": "700"}], "probes": [], "exons": []}}},
    )

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.get("/api/v1/coverage/samples/S1")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["cov_table"], dict)
    assert body["cov_table"]["TP53"]["1"]["cov"] == "700"
