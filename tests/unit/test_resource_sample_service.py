"""ResourceSampleService behavior at persistence and API boundaries."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bson import ObjectId

from api.application.resources.sample import ResourceSampleService
from api.domain.core.exceptions import AppError


class SampleRepository:
    def __init__(self) -> None:
        self.samples = {
            "sample-oid": {
                "_id": "sample-oid",
                "name": "synthetic-sample",
                "asp_id": "assay",
                "ingest_status": "ready",
            }
        }
        self.updated: tuple[object, dict[str, object]] | None = None
        self.search_args: dict[str, object] | None = None

    def search_samples_for_admin(self, **kwargs: object) -> tuple[list[object], int | None]:
        self.search_args = kwargs
        return [self.samples["sample-oid"], "not-a-document"], None

    def get_sample(self, sample_id: str) -> dict[str, object] | None:
        return self.samples.get(sample_id)

    def get_sample_name(self, sample_id: str) -> str | None:
        sample = self.samples.get(sample_id)
        return str(sample["name"]) if sample else None

    def update_sample(self, sample_id: object, sample: dict[str, object]) -> None:
        self.updated = (sample_id, sample)


class AssayPanelRepository:
    def get_all_asps(self, *, is_active: bool | None = None) -> list[dict[str, object]]:
        assert is_active is True
        return [
            {
                "asp_id": "assay",
                "asp_group": "hematology",
                "asp_category": "dna",
                "is_active": True,
            },
            {
                "asp_id": "solid-assay",
                "asp_group": "solid",
                "asp_category": "dna",
                "is_active": True,
            },
        ]


def build_service() -> tuple[ResourceSampleService, SampleRepository, list[object]]:
    sample_repository = SampleRepository()
    dependencies = [
        Mock(name=name)
        for name in (
            "variants",
            "cnvs",
            "coverage",
            "translocs",
            "fusions",
            "biomarkers",
            "pgx",
            "rna_expression",
            "rna_classification",
            "rna_quality",
            "sample_comments",
            "finding_comments",
            "reports",
            "reported_variants",
            "oncokb_public_cache",
        )
    ]
    service = ResourceSampleService(
        sample_repository=sample_repository,
        variant_repository=dependencies[0],
        copy_number_variant_repository=dependencies[1],
        coverage_repository=dependencies[2],
        translocation_repository=dependencies[3],
        fusion_repository=dependencies[4],
        biomarker_repository=dependencies[5],
        pgx_repository=dependencies[6],
        rna_expression_repository=dependencies[7],
        rna_classification_repository=dependencies[8],
        rna_quality_repository=dependencies[9],
        sample_comment_repository=dependencies[10],
        finding_comment_repository=dependencies[11],
        report_repository=dependencies[12],
        reported_variant_repository=dependencies[13],
        oncokb_public_cache_repository=dependencies[14],
        assay_panel_repository=AssayPanelRepository(),
    )
    return service, sample_repository, dependencies


def valid_sample_document(**overrides: object) -> dict[str, object]:
    """Return a complete synthetic DNA sample accepted by the persisted contract."""
    document: dict[str, object] = {
        "_id": "507f191e810c19729de860ea",
        "name": "synthetic-sample",
        "asp_id": "assay",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "synthetic-case",
        "sample_no": 1,
        "paired": False,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SyntheticPanelPipeline",
        "pipeline_version": "1.0.0",
        "files": {"vcf_files": {"path": "/synthetic/sample.vcf"}},
        "case": {"id": "synthetic-case", "ffpe": False},
    }
    document.update(overrides)
    return document


def test_from_store_wires_all_repositories() -> None:
    repositories = {
        name: object()
        for name in (
            "sample_repository",
            "variant_repository",
            "copy_number_variant_repository",
            "coverage_repository",
            "translocation_repository",
            "fusion_repository",
            "biomarker_repository",
            "pgx_repository",
            "rna_expression_repository",
            "rna_classification_repository",
            "rna_quality_repository",
            "sample_comment_repository",
            "finding_comment_repository",
            "report_repository",
            "reported_variant_repository",
            "oncokb_public_cache_repository",
            "assay_panel_repository",
        )
    }
    service = ResourceSampleService.from_store(SimpleNamespace(**repositories))

    for name, repository in repositories.items():
        assert getattr(service, name) is repository


def test_list_payload_filters_non_documents_and_preserves_query_parameters() -> None:
    service, repository, _ = build_service()

    payload = service.list_payload(asp_ids=["assay"], search="synthetic", page=2, per_page=10)

    assert payload["samples"] == [
        {
            "_id": "sample-oid",
            "name": "synthetic-sample",
            "asp_id": "assay",
            "asp_group": "hematology",
            "asp_category": "dna",
            "case_clarity_id": None,
            "control_clarity_id": None,
            "ingest_status": "ready",
        }
    ]
    assert payload["filter_options"] == {
        "asp_group": ["hematology"],
        "asp_id": ["assay"],
    }
    assert payload["pagination"]["total"] == 0
    assert repository.search_args == {
        "asp_ids": ["assay"],
        "search_str": "synthetic",
        "page": 2,
        "per_page": 10,
        "ready_only": False,
    }


def test_list_payload_filters_assays_by_group_and_returns_cascading_options() -> None:
    service, repository, _ = build_service()

    payload = service.list_payload(
        asp_ids=None,
        search="",
        asp_group="solid",
        page=1,
        per_page=30,
    )

    assert payload["filter_options"] == {
        "asp_group": ["hematology", "solid"],
        "asp_id": ["solid-assay"],
    }
    assert repository.search_args is not None
    assert repository.search_args["asp_ids"] == ["solid-assay"]


def test_list_payload_uses_empty_assay_scope_for_unknown_selection() -> None:
    service, repository, _ = build_service()

    service.list_payload(asp_ids=None, search="", asp_id="unknown")

    assert repository.search_args is not None
    assert repository.search_args["asp_ids"] == []


def test_context_payload_returns_sample_and_rejects_unknown_id() -> None:
    service, _, _ = build_service()

    assert service.context_payload(sample_id="sample-oid")["sample"]["name"] == "synthetic-sample"
    with pytest.raises(AppError) as error:
        service.context_payload(sample_id="missing")
    assert error.value.status_code == 404


def test_update_normalizes_copy_without_mutating_request(monkeypatch: pytest.MonkeyPatch) -> None:
    service, repository, _ = build_service()
    timestamp = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    monkeypatch.setattr("api.application.resources.sample.utc_now", lambda: timestamp)
    monkeypatch.setattr(
        "api.application.resources.sample.current_actor", lambda actor: f"actor:{actor}"
    )
    nested_id = "507f1f77bcf86cd799439011"
    request = {"sample": valid_sample_document(name="renamed", nested={"_id": nested_id})}
    original = deepcopy(request)

    result = service.update(sample_id="sample-oid", payload=request, actor_username="admin")

    assert request == original
    assert repository.updated is not None
    sample_id, updated = repository.updated
    assert sample_id == "sample-oid"
    assert updated["_id"] == "sample-oid"
    assert updated["name"] == "renamed"
    assert updated["nested"] == {"_id": ObjectId(nested_id)}
    assert updated["updated_on"] == timestamp
    assert updated["updated_by"] == "actor:admin"
    assert updated["files"]["vcf_files"]["path"] == "/synthetic/sample.vcf"
    assert result["meta"]["sample_name"] == "renamed"
    assert result["meta"]["sample_oid"] == "sample-oid"


def test_update_rejects_unknown_sample_and_missing_document() -> None:
    service, _, _ = build_service()

    with pytest.raises(AppError) as missing_sample:
        service.update(sample_id="missing", payload={"sample": {}}, actor_username="admin")
    assert missing_sample.value.status_code == 404

    with pytest.raises(AppError) as missing_payload:
        service.update(sample_id="sample-oid", payload={}, actor_username="admin")
    assert missing_payload.value.status_code == 400

    with pytest.raises(AppError) as invalid_document:
        service.update(
            sample_id="sample-oid",
            payload={"sample": {"name": "incomplete"}},
            actor_username="admin",
        )
    assert invalid_document.value.status_code == 400
    assert "Invalid samples payload" in invalid_document.value.message


def test_delete_delegates_all_repositories_and_returns_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, sample_repository, dependencies = build_service()
    delete = Mock(
        return_value={
            "sample_name": "synthetic-sample",
            "results": [{"collection": "samples", "deleted": 1}],
        }
    )
    monkeypatch.setattr("api.application.resources.sample.delete_all_sample_traces", delete)

    result = service.delete(sample_id="sample-oid")

    delete.assert_called_once_with(
        "sample-oid",
        sample_repository=sample_repository,
        variant_repository=dependencies[0],
        copy_number_variant_repository=dependencies[1],
        coverage_repository=dependencies[2],
        translocation_repository=dependencies[3],
        fusion_repository=dependencies[4],
        biomarker_repository=dependencies[5],
        pgx_repository=dependencies[6],
        rna_expression_repository=dependencies[7],
        rna_classification_repository=dependencies[8],
        rna_quality_repository=dependencies[9],
        sample_comment_repository=dependencies[10],
        finding_comment_repository=dependencies[11],
        report_repository=dependencies[12],
        reported_variant_repository=dependencies[13],
        oncokb_public_cache_repository=dependencies[14],
    )
    assert result["meta"]["sample_name"] == "synthetic-sample"
    assert result["meta"]["sample_oid"] == "sample-oid"
    assert result["meta"]["results"] == [{"collection": "samples", "deleted": 1}]


def test_delete_rejects_unknown_sample() -> None:
    service, _, _ = build_service()

    with pytest.raises(AppError) as error:
        service.delete(sample_id="missing")
    assert error.value.status_code == 404
