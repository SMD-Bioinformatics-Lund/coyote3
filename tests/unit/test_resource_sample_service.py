"""ResourceSampleService behavior at persistence and API boundaries."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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


class RecordsUtil:
    def __init__(self) -> None:
        self.received: dict[str, object] | None = None

    def restore_object_ids(self, value: dict[str, object]) -> dict[str, object]:
        self.received = value
        value["restored"] = True
        return value


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


def build_service() -> tuple[ResourceSampleService, SampleRepository, RecordsUtil, list[object]]:
    sample_repository = SampleRepository()
    records_util = RecordsUtil()
    dependencies = [
        Mock(name=name)
        for name in ("variants", "cnvs", "coverage", "translocs", "fusions", "biomarkers")
    ]
    service = ResourceSampleService(
        sample_repository=sample_repository,
        variant_repository=dependencies[0],
        copy_number_variant_repository=dependencies[1],
        coverage_repository=dependencies[2],
        translocation_repository=dependencies[3],
        fusion_repository=dependencies[4],
        biomarker_repository=dependencies[5],
        assay_panel_repository=AssayPanelRepository(),
        records_util=records_util,
    )
    return service, sample_repository, records_util, dependencies


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
            "assay_panel_repository",
        )
    }
    records_util = object()
    service = ResourceSampleService.from_store(
        SimpleNamespace(**repositories), records_util=records_util
    )

    for name, repository in repositories.items():
        assert getattr(service, name) is repository
    assert service.records_util is records_util


def test_list_payload_filters_non_documents_and_preserves_query_parameters() -> None:
    service, repository, _, _ = build_service()

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
    service, repository, _, _ = build_service()

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
    service, repository, _, _ = build_service()

    service.list_payload(asp_ids=None, search="", asp_id="unknown")

    assert repository.search_args is not None
    assert repository.search_args["asp_ids"] == []


def test_context_payload_returns_sample_and_rejects_unknown_id() -> None:
    service, _, _, _ = build_service()

    assert service.context_payload(sample_id="sample-oid")["sample"]["name"] == "synthetic-sample"
    with pytest.raises(AppError) as error:
        service.context_payload(sample_id="missing")
    assert error.value.status_code == 404


def test_update_normalizes_copy_without_mutating_request(monkeypatch: pytest.MonkeyPatch) -> None:
    service, repository, records_util, _ = build_service()
    timestamp = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    monkeypatch.setattr("api.application.resources.sample.utc_now", lambda: timestamp)
    monkeypatch.setattr(
        "api.application.resources.sample.current_actor", lambda actor: f"actor:{actor}"
    )
    request = {"sample": {"_id": "untrusted-id", "name": "renamed"}}
    original = deepcopy(request)

    result = service.update(sample_id="sample-oid", payload=request, actor_username="admin")

    assert request == original
    assert records_util.received is not request["sample"]
    assert repository.updated is not None
    sample_id, updated = repository.updated
    assert sample_id == "sample-oid"
    assert updated == {
        "_id": "sample-oid",
        "name": "renamed",
        "updated_on": timestamp,
        "updated_by": "actor:admin",
        "restored": True,
    }
    assert result["meta"]["sample_name"] == "renamed"
    assert result["meta"]["sample_oid"] == "sample-oid"


def test_update_rejects_unknown_sample_and_missing_document() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(AppError) as missing_sample:
        service.update(sample_id="missing", payload={"sample": {}}, actor_username="admin")
    assert missing_sample.value.status_code == 404

    with pytest.raises(AppError) as missing_payload:
        service.update(sample_id="sample-oid", payload={}, actor_username="admin")
    assert missing_payload.value.status_code == 400


def test_delete_delegates_all_repositories_and_returns_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, sample_repository, _, dependencies = build_service()
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
    )
    assert result["meta"]["sample_name"] == "synthetic-sample"
    assert result["meta"]["sample_oid"] == "sample-oid"
    assert result["meta"]["results"] == [{"collection": "samples", "deleted": 1}]


def test_delete_rejects_unknown_sample() -> None:
    service, _, _, _ = build_service()

    with pytest.raises(AppError) as error:
        service.delete(sample_id="missing")
    assert error.value.status_code == 404
