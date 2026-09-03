"""Mongo-compatible integration tests for complete sample data lifecycles."""

from __future__ import annotations

from types import SimpleNamespace

import mongomock
import pytest

from api.application.admin.sample_deletion import delete_all_sample_traces
from api.application.ingest.dependent_writes import cleanup, write_dependents
from api.contracts.operations import OperationResult


class _CollectionDeleteRepository:
    def __init__(self, collection, method_name: str, key: str = "SAMPLE_ID") -> None:
        self.collection = collection
        self.key = key
        setattr(self, method_name, self._delete)

    def _delete(self, sample_id: str) -> OperationResult:
        return OperationResult.from_delete(self.collection.delete_many({self.key: sample_id}))


class _SampleRepository:
    def __init__(self, collection) -> None:
        self.collection = collection

    def get_sample_by_id(self, sample_id: str):
        return self.collection.find_one({"_id": sample_id})

    def delete_sample(self, sample_id: str) -> OperationResult:
        return OperationResult.from_delete(self.collection.delete_one({"_id": sample_id}))


class _IngestService:
    def __init__(self, database) -> None:
        self.database = database
        self.anno_vep_repository = SimpleNamespace(upsert_many=lambda *_args, **_kwargs: None)

    def _collection(self, name: str):
        return self.database[name]

    def _sample_collection(self):
        return self.database.samples

    @staticmethod
    def _provider_sample_id(sample_id: str) -> str:
        return sample_id

    @staticmethod
    def _normalize_collection_docs(_collection: str, docs):
        return docs


def test_failed_dependent_ingest_leaves_no_partial_sample_data(monkeypatch) -> None:
    database = mongomock.MongoClient().coyote3_test
    service = _IngestService(database)
    sample_id = "sample-rollback"
    database.samples.insert_one({"_id": sample_id, "name": "SYNTHETIC_ROLLBACK"})

    original_insert_many = database.cnvs.insert_many

    def fail_cnv_write(*_args, **_kwargs):
        raise RuntimeError("synthetic dependent write failure")

    monkeypatch.setattr(database.cnvs, "insert_many", fail_cnv_write)
    with pytest.raises(RuntimeError, match="synthetic dependent write failure"):
        write_dependents(
            service,
            preload={
                "snvs": [{"simple_id": "1:100:A:T"}],
                "cnvs": [{"genes": ["GENE1"]}],
            },
            sample_id=sample_id,
            sample_name="SYNTHETIC_ROLLBACK",
        )
    monkeypatch.setattr(database.cnvs, "insert_many", original_insert_many)

    cleanup(service, sample_id)

    assert database.samples.count_documents({"_id": sample_id}) == 0
    assert database.variants.count_documents({"SAMPLE_ID": sample_id}) == 0
    assert database.cnvs.count_documents({"SAMPLE_ID": sample_id}) == 0


def test_delete_all_sample_traces_removes_every_owned_document() -> None:
    database = mongomock.MongoClient().coyote3_test
    sample_id = "sample-delete"
    sample_name = "SYNTHETIC_DELETE"
    database.samples.insert_one({"_id": sample_id, "name": sample_name})

    repository_specs = {
        "variant_repository": ("variants", "delete_sample_variants"),
        "copy_number_variant_repository": ("cnvs", "delete_sample_cnvs"),
        "coverage_repository": ("panel_coverage", "delete_sample_coverage"),
        "translocation_repository": ("translocations", "delete_sample_translocs"),
        "fusion_repository": ("fusions", "delete_sample_fusions"),
        "biomarker_repository": ("biomarkers", "delete_sample_biomarkers"),
        "pgx_repository": ("pgx", "delete_sample_pgx"),
        "rna_expression_repository": ("rna_expression", "delete_sample_expression"),
        "rna_classification_repository": (
            "rna_classification",
            "delete_sample_classification",
        ),
        "rna_quality_repository": ("rna_qc", "delete_sample_qc"),
        "sample_comment_repository": ("sample_comments", "delete_sample_comments", "SAMPLE_ID"),
        "finding_comment_repository": (
            "finding_comments",
            "delete_sample_finding_comments",
            "sample_oid",
        ),
        "report_repository": ("reports", "delete_sample_reports", "SAMPLE_ID"),
        "reported_variant_repository": (
            "reported_variants",
            "delete_sample_reported_variants",
            "SAMPLE_ID",
        ),
    }
    repository_specs = {
        name: spec if len(spec) == 3 else (*spec, "SAMPLE_ID")
        for name, spec in repository_specs.items()
    }
    repositories = {}
    for argument_name, (collection_name, method_name, key) in repository_specs.items():
        database[collection_name].insert_one({key: sample_id, "value": collection_name})
        repositories[argument_name] = _CollectionDeleteRepository(
            database[collection_name], method_name, key
        )
    summary = delete_all_sample_traces(
        sample_id,
        sample_repository=_SampleRepository(database.samples),
        **repositories,
    )

    assert summary["sample_name"] == sample_name
    assert database.samples.count_documents({"_id": sample_id}) == 0
    for collection_name, _method_name, key in repository_specs.values():
        assert database[collection_name].count_documents({key: sample_id}) == 0
    assert all(result["ok"] for result in summary["results"])
