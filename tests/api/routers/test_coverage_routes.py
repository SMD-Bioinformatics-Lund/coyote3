"""Behavior tests for Coverage API routes."""

from __future__ import annotations

import pytest
from api.domain.core.exceptions import AppError

from api.contracts.coverage import CoverageSamplePayload
from api.app.container import store
from api.interfaces.http import coverage
from api.security.access import ApiUser
from api.application.sample import coverage as coverage_service_module
from api.application.sample.coverage import CoverageService
from tests.fixtures.api import mock_collections as fx


def _coverage_service() -> CoverageService:
    return CoverageService(
        assay_configuration_repository=store.assay_configuration_repository,
        assay_panel_repository=store.assay_panel_repository,
        gene_list_repository=store.gene_list_repository,
        coverage_repository=store.coverage_repository,
        grouped_coverage_repository=store.grouped_coverage_repository,
    )


def test_coverage_sample_read_builds_payload(monkeypatch):
    """Test coverage sample read builds payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["filters"] = {"snvlists": ["GL1"]}
    sample["assay"] = "WGS"
    sample["profile"] = "production"
    service = _coverage_service()

    monkeypatch.setattr(coverage, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(
        service.assay_configuration_repository,
        "get_aspc_no_meta",
        lambda assay, profile: {"assay_group": "dna"},
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        lambda asp_name: {"asp_id": "WGS", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        coverage.util.common,
        "get_sample_effective_genes",
        lambda sample, assay_panel_doc, checked_snvlists_genes_dict: (["TP53", "NPM1"], ["TP53"]),
    )
    monkeypatch.setattr(
        service.gene_list_repository, "get_isgl_by_ids", lambda ids: {"GL1": {"genes": ["TP53"]}}
    )
    monkeypatch.setattr(
        service.coverage_repository,
        "get_sample_coverage",
        lambda sample_id: {"_id": "cov1", "TP53": {"mean": 700}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "filter_genes_from_form",
        lambda cov_dict, filter_genes, assay_group, *, grouped_coverage_repository=None: cov_dict,
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "find_low_covered_genes",
        lambda filtered_dict, cutoff, assay_group, *, grouped_coverage_repository=None: filtered_dict,
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "coverage_table",
        lambda filtered_dict, cutoff: {"TP53": {"1": {"cov": 700}}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "organize_data_for_d3",
        lambda filtered_dict: {"genes": [{"name": "TP53"}]},
    )
    monkeypatch.setattr(coverage.util.common, "convert_to_serializable", lambda payload: payload)

    payload = coverage.coverage_sample_read(
        "S1", cov_cutoff=500, user=fx.api_user(), service=service
    )

    assert payload["cov_cutoff"] == 500
    assert payload["smp_grp"] == "dna"
    assert payload["snvlists"] == ["GL1"]
    assert payload["cov_table"]["TP53"]["1"]["cov"] == 700


def test_coverage_blacklisted_read_denies_non_member_group():
    """Test coverage blacklisted read denies non member group.

    Returns:
        The function result.
    """
    user = _route_test_user()
    user.assay_groups = ["rna"]

    with pytest.raises(AppError) as exc:
        coverage.coverage_blacklisted_read("dna", user=user, service=_coverage_service())

    assert exc.value.status_code == 403
    assert "outside your scope" in exc.value.detail["error"]


def _route_test_user() -> ApiUser:
    """Route test user.

    Returns:
            The  route test user result.
    """
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="user",
        roles=["user"],
        access_level=9,
        permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
        auth_type=["local"],
    )


def test_coverage_sample_read_validates_cov_table_dict_shape(monkeypatch):
    """Test coverage sample read validates cov table dict shape.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["filters"] = {"snvlists": ["GL1"]}
    sample["assay"] = "WGS"
    sample["profile"] = "production"
    sample["_id"] = "S1"

    service = _coverage_service()
    monkeypatch.setattr(coverage, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(
        service.assay_configuration_repository,
        "get_aspc_no_meta",
        lambda assay, profile: {"assay_group": "dna"},
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        lambda asp_name: {"asp_id": "WGS", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        coverage.util.common,
        "get_sample_effective_genes",
        lambda sample, assay_panel_doc, checked_snvlists_genes_dict: (["TP53", "NPM1"], ["TP53"]),
    )
    monkeypatch.setattr(
        service.gene_list_repository, "get_isgl_by_ids", lambda ids: {"GL1": {"genes": ["TP53"]}}
    )
    monkeypatch.setattr(
        service.coverage_repository,
        "get_sample_coverage",
        lambda sample_id: {"_id": "cov1", "genes": {"TP53": {"CDS": {"1": {"cov": "700"}}}}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "filter_genes_from_form",
        lambda cov_dict, filter_genes, assay_group, *, grouped_coverage_repository=None: cov_dict,
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "find_low_covered_genes",
        lambda filtered_dict, cutoff, assay_group, *, grouped_coverage_repository=None: filtered_dict,
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "coverage_table",
        lambda filtered_dict, cutoff: {"TP53": {"1": {"cov": "700"}}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "organize_data_for_d3",
        lambda filtered_dict: {
            "genes": {"TP53": {"CDS": [{"cov": "700"}], "probes": [], "exons": []}}
        },
    )

    body = coverage.coverage_sample_read(
        "S1",
        cov_cutoff=500,
        user=_route_test_user(),
        service=service,
    )
    CoverageSamplePayload.model_validate(body)
    assert isinstance(body["cov_table"], dict)
    assert body["cov_table"]["TP53"]["1"]["cov"] == "700"
