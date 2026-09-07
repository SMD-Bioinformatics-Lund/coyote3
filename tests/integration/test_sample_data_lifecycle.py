"""Required transaction boundaries tested against a disposable MongoDB replica set."""

import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from bson import ObjectId
from pymongo import MongoClient

from api.application.ingest.service import InternalIngestService
from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.mongo.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repositories.ingest_jobs import IngestJobsRepository
from api.infra.mongo.repositories.revision_rotation import rotate_active_revision
from api.infra.mongo.repositories.sample_deletion import delete_all_sample_traces


def test_bulk_update_failure_aborts_all_documents(database, monkeypatch):
    repository = BaseRepository(SimpleNamespace())
    collection = database.values
    repository.set_collection(collection)
    collection.insert_many([{"value": 0}, {"value": 0}])
    original = collection.update_many

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic post-write failure")

    monkeypatch.setattr(collection, "update_many", fail)
    with pytest.raises(RuntimeError, match="post-write failure"):
        repository.update_many_atomic({}, {"$set": {"value": 1}})
    assert collection.count_documents({"value": 0}) == 2


def test_public_catalogue_refresh_failure_restores_both_products(database, monkeypatch):
    repository = OncoKbPublicCacheRepository(
        SimpleNamespace(
            oncokb_public_collection=database.oncokb_public,
            oncokb_genes_public_collection=database.oncokb_genes_public,
            oncokb_cancer_genes_public_collection=database.oncokb_cancer_genes_public,
        )
    )
    repository.gene_collection.insert_one({"gene": "OLD"})
    repository.cancer_gene_collection.insert_one({"gene": "OLD"})

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic pruning failure")

    monkeypatch.setattr(repository.gene_collection, "delete_many", fail)
    with pytest.raises(RuntimeError, match="pruning failure"):
        repository.refresh_gene_markers([{"gene": "NEW"}], [{"gene": "NEW"}])
    assert [doc["gene"] for doc in repository.gene_collection.find()] == ["OLD"]
    assert [doc["gene"] for doc in repository.cancer_gene_collection.find()] == ["OLD"]


def test_concurrent_revision_rotation_has_one_winner(database):
    collection = database.asp
    collection.insert_one({"asp_id": "synthetic", "version": 1, "is_active": True})

    def rotate(index):
        try:
            rotate_active_revision(
                collection,
                selector={"asp_id": "synthetic"},
                expected_version=1,
                new_document={"asp_id": "synthetic", "version": 2, "is_active": True},
                retire_fields={},
            )
            return "committed"
        except RuntimeError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(rotate, range(2))) == ["committed", "conflict"]
    assert collection.count_documents({"is_active": True}) == 1
    assert collection.count_documents({"version": 2}) == 1


@pytest.fixture
def database():
    uri = os.getenv("LIFECYCLE_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set LIFECYCLE_TEST_MONGO_URI for disposable transaction tests")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    database = client[f"coyote3_lifecycle_test_{uuid4().hex}"]
    try:
        yield database
    finally:
        client.drop_database(database.name)
        client.close()


@pytest.fixture
def service(database, monkeypatch):
    gateway = IngestCollectionGateway(
        collections={name: database[name] for name in ("samples", "variants", "cnvs", "anno_vep")}
    )
    service = InternalIngestService(
        collection_gateway=gateway,
        anno_vep_repository=SimpleNamespace(upsert_many=lambda *args, **kwargs: None),
        invalidate_dashboard_metrics=lambda: None,
    )
    monkeypatch.setattr(service, "_validate_payload_file_keys", lambda payload: payload)
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda payload: set())
    monkeypatch.setattr(service, "_apply_resolved_aspc_snapshot", lambda payload: payload)
    monkeypatch.setattr(service, "_validate_preload_matches_declared_files", lambda **kwargs: None)
    monkeypatch.setattr(service, "_normalize_collection_docs", lambda name, docs: docs)
    monkeypatch.setattr(
        service,
        "_parse_preload",
        lambda payload: {
            "snvs": [{"simple_id": "1:100:A:T"}],
            "cnvs": [{"genes": ["SYNTHETIC"]}],
        },
    )
    return service


def payload(**changes):
    return {
        "name": "SYNTHETIC",
        "asp_id": "synthetic",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "synthetic-case",
        "sample_no": 1,
        "paired": False,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SyntheticPipeline",
        "pipeline_version": "1.0.0",
        "files": {"vcf_files": {"path": "/synthetic/input.vcf"}},
        "case": {"id": "synthetic-case", "ffpe": False},
        **changes,
    }


def test_create_failure_aborts_all_writes(database, service, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic CNV failure")

    monkeypatch.setattr(service.collection_gateway.collection("cnvs"), "insert_many", fail)
    with pytest.raises(RuntimeError, match="CNV failure"):
        service.ingest_sample_bundle(payload())
    for name in ("samples", "variants", "cnvs"):
        assert database[name].count_documents({}) == 0


def test_update_failure_restores_original_evidence_and_metadata(database, service):
    created = service.ingest_sample_bundle(payload())
    before = {name: list(database[name].find()) for name in ("samples", "variants", "cnvs")}

    def fail_receipt(result, session):
        assert result["sample_id"] == created["sample_id"]
        raise RuntimeError("synthetic receipt failure")

    with pytest.raises(RuntimeError, match="receipt failure"):
        service.ingest_sample_bundle(
            payload(pipeline_version="2.0.0"), allow_update=True, record_completion=fail_receipt
        )
    assert before == {name: list(database[name].find()) for name in before}


def test_update_success_replaces_evidence_and_metadata_together(database, service):
    created = service.ingest_sample_bundle(payload())
    old_id = database.variants.find_one()["_id"]
    result = service.ingest_sample_bundle(payload(pipeline_version="2.0.0"), allow_update=True)
    assert result["sample_id"] == created["sample_id"]
    assert database.samples.find_one()["pipeline_version"] == "2.0.0"
    assert database.samples.find_one()["ingest_status"] == "ready"
    assert database.variants.count_documents({}) == 1
    assert database.variants.find_one()["_id"] != old_id


def test_job_receipt_is_atomic_with_bundle_and_fences_stale_worker(database, service):
    jobs = IngestJobsRepository(SimpleNamespace(ingest_jobs_collection=database.ingest_jobs))
    job_id = jobs.submit(source_payload=payload(), submitted_by="synthetic")
    job = jobs.claim(job_id, lease_seconds=10)
    with pytest.raises(RuntimeError, match="lease changed"):
        service.ingest_sample_bundle(
            payload(),
            record_completion=lambda result, session: jobs.complete(
                job_id, "stale-token", result, session
            ),
        )
    assert database.samples.count_documents({}) == 0
    assert jobs.get(job_id)["state"] == "running"
    result = service.ingest_sample_bundle(
        payload(),
        record_completion=lambda result, session: jobs.complete(
            job_id, job["lease_token"], result, session
        ),
    )
    assert jobs.get(job_id)["result"] == result
    assert jobs.get(job_id)["state"] == "succeeded"
    assert jobs.get(job_id)["source_payload"] is None


def test_ignored_duplicates_do_not_allow_partial_batch_failure(database):
    gateway = IngestCollectionGateway(
        collections={"samples": database.samples, "values": database.values}
    )
    database.values.insert_one({"_id": "existing"})
    result = gateway.insert_documents(
        "values", [{"_id": "first"}, {"_id": "existing"}, {"_id": "last"}], ignore_duplicates=True
    )
    assert result["inserted_count"] == 2
    assert database.values.count_documents({}) == 3
    with pytest.raises(Exception):
        gateway.insert_documents("values", [{"_id": "rolled-back"}, {"_id": "existing"}])
    assert database.values.find_one({"_id": "rolled-back"}) is None


def test_revision_rotation_failure_keeps_original_active(database, monkeypatch):
    collection = database.asp
    collection.insert_one({"asp_id": "synthetic", "version": 1, "is_active": True})
    monkeypatch.setattr(
        collection,
        "insert_one",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )
    with pytest.raises(RuntimeError, match="synthetic failure"):
        rotate_active_revision(
            collection,
            selector={"asp_id": "synthetic"},
            expected_version=1,
            new_document={"asp_id": "synthetic", "version": 2, "is_active": True},
            retire_fields={},
        )
    assert database.asp.find_one()["is_active"] is True


@pytest.mark.parametrize("fail", [False, True])
def test_sample_deletion_is_atomic_and_preserves_other_owners(database, monkeypatch, fail):
    oid = ObjectId()
    database.samples.insert_one({"_id": oid, "name": "SYNTHETIC_DELETE"})
    specs = {
        "variant": "variants",
        "copy_number_variant": "cnvs",
        "coverage": "panel_coverage",
        "translocation": "translocations",
        "fusion": "fusions",
        "biomarker": "biomarkers",
        "pgx": "pgx",
        "rna_expression": "rna_expression",
        "rna_classification": "rna_classification",
        "rna_quality": "rna_qc",
        "sample_comment": "sample_comments",
        "finding_comment": "finding_comments",
        "report": "reports",
        "reported_variant": "reported_variants",
    }
    repositories = {}
    for key, name in specs.items():
        field = (
            "sample_oid"
            if key in {"sample_comment", "finding_comment", "report", "reported_variant"}
            else "SAMPLE_ID"
        )
        database[name].insert_many(
            [{field: oid if field == "sample_oid" else str(oid)}, {field: "other-owner"}]
        )
        repositories[f"{key}_repository"] = SimpleNamespace(
            get_collection=lambda collection=database[name]: collection,
            invalidate_dashboard_metrics=lambda: None,
        )
    samples = SimpleNamespace(
        adapter=SimpleNamespace(client=database.client),
        get_collection=lambda: database.samples,
        invalidate_dashboard_metrics=lambda: None,
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.sample_deletion.invalidate_samples_cache",
        lambda adapter: None,
    )
    if fail:
        monkeypatch.setattr(
            repositories["report_repository"].get_collection(),
            "delete_many",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("synthetic deletion failure")
            ),
        )
        with pytest.raises(RuntimeError, match="deletion failure"):
            delete_all_sample_traces(str(oid), sample_repository=samples, **repositories)
    else:
        assert (
            delete_all_sample_traces(str(oid), sample_repository=samples, **repositories)[
                "sample_name"
            ]
            == "SYNTHETIC_DELETE"
        )
    assert database.samples.count_documents({}) == (1 if fail else 0)
    for name in specs.values():
        assert database[name].count_documents({}) == (2 if fail else 1)
