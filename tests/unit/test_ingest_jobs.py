"""Durable delivery, fenced receipts, and worker replay behavior with synthetic jobs."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest
from pymongo.errors import AutoReconnect

from api.application.ingest.jobs import job_status_payload, submit_ingest_job
from api.infra.mongo.repositories.ingest_jobs import IngestJobsRepository
from api.tasks import ingest


@pytest.fixture
def jobs(monkeypatch):
    repository = IngestJobsRepository(
        SimpleNamespace(ingest_jobs_collection=mongomock.MongoClient().test.ingest_jobs)
    )
    monkeypatch.setattr(ingest, "get_ingest_jobs_repository", lambda: repository)
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "task_family_enabled", lambda family: True)
    monkeypatch.setattr(ingest, "_record_ingest_audit", lambda *args, **kwargs: None)
    return repository


@pytest.mark.parametrize(
    "kind,task,method",
    [
        ("sample_bundle", ingest.ingest_sample_bundle_task, "ingest_sample_bundle"),
        ("insert_document", ingest.insert_collection_document_task, "insert_collection_document"),
        (
            "insert_documents",
            ingest.insert_collection_documents_task,
            "insert_collection_documents",
        ),
        ("upsert_document", ingest.upsert_collection_document_task, "upsert_collection_document"),
    ],
)
def test_duplicate_delivery_returns_committed_result_once(jobs, monkeypatch, kind, task, method):
    calls = []

    def execute(*args, record_completion, **kwargs):
        calls.append(kwargs)
        result = {"status": "ok", "written": 1}
        record_completion(result, None)
        return result

    service = SimpleNamespace(
        **{
            name: execute
            for name in (
                "ingest_sample_bundle",
                "insert_collection_document",
                "insert_collection_documents",
                "upsert_collection_document",
            )
        }
    )
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: service)
    identity = jobs.submit(source_payload={}, kind=kind, submitted_by="synthetic")
    assert task.run(job_id=identity) == task.run(job_id=identity) == {"status": "ok", "written": 1}
    assert len(calls) == 1
    assert jobs.get(identity)["source_payload"] is None


@pytest.mark.parametrize(
    "failure,retryable", [(AutoReconnect("unavailable"), True), (ValueError("invalid"), False)]
)
def test_failed_attempt_retains_staged_input(jobs, monkeypatch, tmp_path, failure, retryable):
    staged = tmp_path / "input"
    staged.mkdir()
    (staged / "synthetic.vcf").write_text("synthetic")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(
        ingest, "get_internal_ingest_service", lambda: SimpleNamespace(ingest_sample_bundle=fail)
    )
    identity = jobs.submit(source_payload={}, staging_dir=str(staged), submitted_by="synthetic")
    with pytest.raises(type(failure)):
        ingest.ingest_sample_bundle_task.run(job_id=identity)
    assert jobs.get(identity)["state"] == ("pending" if retryable else "failed")
    assert staged.exists()


def test_lost_acknowledgement_uses_the_committed_receipt(jobs, monkeypatch, tmp_path):
    staging = tmp_path / "input"
    staging.mkdir()

    def committed(*args, record_completion, **kwargs):
        record_completion({"status": "ok"}, None)
        raise AutoReconnect("synthetic lost acknowledgement")

    monkeypatch.setattr(
        ingest,
        "get_internal_ingest_service",
        lambda: SimpleNamespace(ingest_sample_bundle=committed),
    )
    identity = jobs.submit(source_payload={}, staging_dir=str(staging), submitted_by="synthetic")
    assert ingest.ingest_sample_bundle_task.run(job_id=identity) == {"status": "ok"}
    assert jobs.get(identity)["state"] == "succeeded"
    assert not staging.exists()


def test_broker_outage_does_not_lose_accepted_job(jobs):
    def unavailable(identity):
        assert jobs.get(identity)["state"] == "pending"
        raise OSError("synthetic broker failure")

    identity = submit_ingest_job(jobs, unavailable, source_payload={}, submitted_by="synthetic")
    assert jobs.get(identity)["state"] == "pending"
    assert jobs.pending()[0]["_id"] == identity


def test_expired_worker_cannot_complete_or_fail_reclaimed_job(jobs):
    identity = jobs.submit(source_payload={}, submitted_by="synthetic")
    first = jobs.claim(identity, lease_seconds=30)
    assert jobs.claim(identity, lease_seconds=30) is None
    jobs.get_collection().update_one(
        {"_id": identity},
        {"$set": {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    assert jobs.pending()[0]["_id"] == identity
    second = jobs.claim(identity, lease_seconds=30)
    assert first["lease_token"] != second["lease_token"]
    with pytest.raises(RuntimeError, match="lease changed"):
        jobs.complete(identity, first["lease_token"], {}, None)
    jobs.fail(identity, first["lease_token"], retryable=False)
    assert jobs.get(identity)["state"] == "running"
    jobs.complete(identity, second["lease_token"], {"status": "ok"}, None)
    assert jobs.pending() == []


def test_disabled_execution_leaves_job_pending(jobs, monkeypatch):
    identity = jobs.submit(source_payload={}, submitted_by="synthetic")
    monkeypatch.setattr(ingest, "task_family_enabled", lambda family: False)
    ingest.ingest_sample_bundle_task.run(job_id=identity)
    assert jobs.get(identity)["state"] == "pending"
    assert jobs.get(identity)["attempts"] == 0


def test_dispatcher_only_publishes_identifiers(jobs, monkeypatch):
    identity = jobs.submit(source_payload={"name": "synthetic"}, submitted_by="synthetic")
    published = []
    monkeypatch.setattr(
        ingest.ingest_sample_bundle_task, "apply_async", lambda **kwargs: published.append(kwargs)
    )
    assert ingest.dispatch_pending_jobs.run()["dispatched"] == 1
    assert published[0]["kwargs"] == {"job_id": identity}
    assert published[0]["task_id"] == identity


def test_status_never_exposes_payload_or_worker_lease(jobs):
    identity = jobs.submit(source_payload={"name": "synthetic"}, submitted_by="synthetic")
    status = job_status_payload(jobs.get(identity))
    assert status["state"] == "PENDING"
    assert not {"source_payload", "lease_token", "staging_dir"}.intersection(status)


def test_disabled_family_backlog_cannot_starve_enabled_jobs(jobs, monkeypatch):
    for _ in range(101):
        jobs.submit(source_payload={}, submitted_by="synthetic")
    identity = jobs.submit(source_payload={}, submitted_by="synthetic", kind="insert_document")
    monkeypatch.setattr(ingest, "task_family_enabled", lambda family: family == "collection_writes")
    published = []
    monkeypatch.setattr(
        ingest.insert_collection_document_task,
        "apply_async",
        lambda **kwargs: published.append(kwargs),
    )
    assert ingest.dispatch_pending_jobs.run()["dispatched"] == 1
    assert published[0]["task_id"] == identity
