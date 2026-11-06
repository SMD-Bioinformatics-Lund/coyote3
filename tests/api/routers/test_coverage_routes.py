"""Behavior tests for Coverage API routes."""

from __future__ import annotations

import pytest

from api.app.container import store
from api.interfaces.http.v1.clinical.dna import coverage
from api.security.access import ApiUser
from coyote3.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote3.application.sample import coverage as coverage_service_module
from coyote3.application.sample.coverage import CoverageService
from coyote3.contracts.coverage import CoverageSamplePayload
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


def _coverage_configuration(assay, profile, diagnosis):
    """Provide a complete synthetic configuration revision for coverage requests."""
    return {
        **fx.assay_config_doc(),
        "asp_id": assay,
        "aspc_id": f"{assay}_{diagnosis}_{profile}",
        "diagnosis_id": diagnosis,
        "environment": profile,
        "version": 1,
        "assay_resource_release": capture_assay_resource(_coverage_assay()),
        "gene_list_release": capture_gene_lists(
            [{"isgl_id": "GL1", "genes": ["TP53", "ALK"], "is_active": True, "list_type": ["snv"]}]
        ),
    }


def _coverage_assay(asp_name=None, **_kwargs):
    """Provide the synthetic WGS assay referenced by coverage fixtures."""
    return {
        "asp_id": "wgs",
        "covered_genes": ["TP53", "NPM1"],
        "asp_group": "dna",
        "asp_family": "wgs",
        "asp_category": "dna",
        "version": 1,
    }


def _coverage_service() -> CoverageService:
    return CoverageService(
        assay_configuration_repository=store.assay_configuration_repository,
        assay_panel_repository=store.assay_panel_repository,
        d4_coverage_repository=store.d4_coverage_repository,
        d4_coverage_blacklist_repository=store.d4_coverage_blacklist_repository,
    )


@pytest.mark.parametrize("gene_list_id", [None, "GL1"])
def test_coverage_sample_read_builds_payload(monkeypatch, gene_list_id):
    sample = fx.sample_doc()
    sample["filters"] = {"somatic": {"snv": {"snvlists": ["GL1"]}}}
    sample["asp_id"] = "wgs"
    sample["diagnosis_id"] = "myeloid"
    sample["environment"] = "production"
    service = _coverage_service()
    requested_diagnoses: list[str] = []
    requested_gene_scopes: list[list[str]] = []

    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    monkeypatch.setattr(
        service.assay_configuration_repository,
        "get_aspc_no_meta",
        lambda assay, profile, diagnosis: (
            requested_diagnoses.append(diagnosis)
            or (_coverage_configuration(assay, profile, diagnosis) if diagnosis == "base" else None)
        ),
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        _coverage_assay,
    )
    monkeypatch.setattr(
        service.d4_coverage_repository,
        "get_sample_coverage",
        lambda sample_id: {"_id": "cov1", "TP53": {"mean": 700}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "filter_genes_from_form",
        lambda cov_dict, filter_genes, assay_group, *, d4_coverage_blacklist_repository=None: (
            requested_gene_scopes.append(filter_genes) or cov_dict
        ),
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "find_low_covered_genes",
        lambda filtered_dict, cutoff, assay_group, *, d4_coverage_blacklist_repository=None: (
            filtered_dict
        ),
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
        "S1",
        cov_cutoff=500,
        user=fx.api_user(),
        service=sdk_fixtures.sample_operations(service, fx.api_user()),
        gene_list_id=gene_list_id,
    )

    assert payload["cov_cutoff"] == 500
    assert payload["smp_grp"] == "dna"
    expected_scope = ["TP53"] if gene_list_id else ["NPM1", "TP53"]
    assert payload["gene_scope"] == expected_scope
    assert payload["gene_list_id"] == gene_list_id
    assert payload["cov_table"]["TP53"]["1"]["cov"] == 700
    assert requested_diagnoses == ["myeloid", "base"]
    assert requested_gene_scopes == [expected_scope]


@pytest.mark.parametrize(
    "genes,expected",
    [
        (["TP53", "ALK"], ["TP53"]),
        ({"NPM1": {"description": "Synthetic"}}, ["NPM1"]),
        ([], []),
        (["ALK"], []),
    ],
)
def test_optional_coverage_gene_list_only_narrows_assay_scope(monkeypatch, genes, expected):
    """Captured list selection cannot admit outside-assay genes or broaden empty lists."""
    service = _coverage_service()
    configuration = _coverage_configuration("wgs", "production", "base")
    configuration["gene_list_release"] = capture_gene_lists(
        [{"isgl_id": "focused", "displayname": "Focused genes", "genes": genes}]
    )
    monkeypatch.setattr(
        coverage_service_module, "get_formatted_assay_config", lambda *args, **kwargs: configuration
    )
    monkeypatch.setattr(service.d4_coverage_repository, "get_sample_coverage", lambda _: {})
    monkeypatch.setattr(
        service.d4_coverage_blacklist_repository, "get_regions_per_group", lambda _: []
    )
    result = service.sample_payload(
        sample={"_id": "SYNTHETIC", "asp_id": "wgs"}, cov_cutoff=20, gene_list_id="focused"
    )
    assert result["gene_scope"] == expected
    assert result["gene_lists"] == [{"id": "focused", "label": "Focused genes"}]
    with pytest.raises(AppError) as error:
        service.sample_payload(
            sample={"_id": "SYNTHETIC", "asp_id": "wgs"}, cov_cutoff=20, gene_list_id="unavailable"
        )
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "filters",
    [
        {"somatic": {"snv": {"snvlists": ["GL1"]}}},
        {"somatic": {"snv": {"adhoc_genes": {"genes": {"ALK": True}}}}},
        {},
    ],
)
@pytest.mark.parametrize("covered_genes", [["TP53", "NPM1"], [], None])
@pytest.mark.parametrize("has_measurements", [True, False])
def test_coverage_scope_uses_captured_assay_not_finding_filters(
    monkeypatch, filters, covered_genes, has_measurements
):
    """Use recorded assay genes, with ingested-gene fallback for unspecified scope."""
    service = _coverage_service()
    configuration = _coverage_configuration("wgs", "production", "base")
    assay = _coverage_assay()
    if covered_genes is None:
        assay.pop("covered_genes")
    else:
        assay["covered_genes"] = covered_genes
    configuration["assay_resource_release"] = capture_assay_resource(assay)
    monkeypatch.setattr(
        coverage_service_module, "get_formatted_assay_config", lambda *args, **kwargs: configuration
    )
    source = {
        "genes": {
            gene: {"CDS": {"1": {"chr": "1", "start": 0, "end": 100, "nbr": 1, "cov": 5}}}
            for gene in ("TP53", "NPM1", "ALK")
            if has_measurements
        }
    }
    monkeypatch.setattr(service.d4_coverage_repository, "get_sample_coverage", lambda _: source)
    monkeypatch.setattr(
        service.d4_coverage_blacklist_repository, "get_regions_per_group", lambda _: []
    )

    def reject_latest_assay(*args, **kwargs):
        """Coverage must not replace the sample's captured assay with a newer revision."""
        raise AssertionError("Unexpected live assay lookup")

    monkeypatch.setattr(service.assay_panel_repository, "get_asp", reject_latest_assay)
    result = service.sample_payload(
        sample={"_id": "SYNTHETIC", "asp_id": "wgs", "filters": filters}, cov_cutoff=20
    )
    expected = sorted(covered_genes or source["genes"])
    assert result["gene_scope"] == expected
    expected_measured = sorted(set(expected) & source["genes"].keys())
    assert sorted(result["coverage"].get("genes", {})) == expected_measured
    assert sorted(result["cov_table"]) == expected_measured
    if has_measurements:
        assert isinstance(source["genes"]["TP53"]["CDS"], dict)


def test_coverage_blacklisted_read_denies_non_member_group():
    user = _route_test_user()
    user.asp_groups = ["rna"]

    with pytest.raises(AppError) as exc:
        coverage.coverage_blacklisted_read(
            "dna", user=user, service=sdk_fixtures.coverage_operations(_coverage_service(), user)
        )

    assert exc.value.status_code == 403
    assert "outside your scope" in exc.value.detail["error"]


def _route_test_user() -> ApiUser:
    """Route test user."""
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="user",
        roles=["user"],
        access_level=9,
        permissions=[],
        asp_ids=["wgs"],
        asp_groups=["dna"],
        envs=["production"],
        asp_map={},
        auth_type=["local"],
    )


def test_coverage_sample_read_validates_cov_table_dict_shape(monkeypatch):
    sample = fx.sample_doc()
    sample["filters"] = {"somatic": {"snv": {"snvlists": ["GL1"]}}}
    sample["asp_id"] = "wgs"
    sample["diagnosis_id"] = "base"
    sample["environment"] = "production"
    sample["_id"] = "S1"

    service = _coverage_service()
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda sample_id, user: sample)
    monkeypatch.setattr(
        service.assay_configuration_repository,
        "get_aspc_no_meta",
        _coverage_configuration,
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        _coverage_assay,
    )
    monkeypatch.setattr(
        service.d4_coverage_repository,
        "get_sample_coverage",
        lambda sample_id: {"_id": "cov1", "genes": {"TP53": {"CDS": {"1": {"cov": "700"}}}}},
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "filter_genes_from_form",
        lambda cov_dict, filter_genes, assay_group, *, d4_coverage_blacklist_repository=None: (
            cov_dict
        ),
    )
    monkeypatch.setattr(
        coverage_service_module.CoverageProcessingService,
        "find_low_covered_genes",
        lambda filtered_dict, cutoff, assay_group, *, d4_coverage_blacklist_repository=None: (
            filtered_dict
        ),
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
        service=sdk_fixtures.sample_operations(service, _route_test_user()),
    )
    CoverageSamplePayload.model_validate(body)
    assert isinstance(body["cov_table"], dict)
    assert body["cov_table"]["TP53"]["1"]["cov"] == "700"
