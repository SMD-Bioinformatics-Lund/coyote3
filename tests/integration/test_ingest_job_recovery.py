"""Lease races and process/commit failures against runner-owned MongoDB only."""

import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from coyote.application.ingest.worker import IngestJobRunner
from coyote_mongo.repositories.ingest_jobs import IngestJobsRepository
from coyote_mongo.transactions import run_transaction
from pymongo import MongoClient, monitoring
from pymongo.uri_parser import parse_uri

from tests.fixtures.mongo_settings import mongo_runtime


class CommitCommands(monitoring.CommandListener):
    def __init__(self):
        self.count = 0

    def started(self, event):
        if event.command_name == "commitTransaction":
            self.count += 1

    def succeeded(self, event):
        pass

    def failed(self, event):
        pass


@pytest.fixture
def database():
    uri = os.getenv("LIFECYCLE_TEST_MONGO_URI")
    if os.getenv("COYOTE4_RUN_DISPOSABLE_TESTS") != "1" or not uri:
        pytest.skip("Run with scripts/quality/run_transaction_tests.py")
    parsed = parse_uri(uri)
    assert all(host == "127.0.0.1" for host, _ in parsed["nodelist"])
    assert parsed["options"].get("replicaSet", "").startswith("coyote-validation-")
    commits = CommitCommands()
    with MongoClient(uri, event_listeners=[commits]) as client:
        db = client[f"coyote4_job_recovery_test_{uuid4().hex}"]
        try:
            yield db, commits, uri
        finally:
            client.admin.command({"configureFailPoint": "failCommand", "mode": "off"})
            client.drop_database(db.name)


def jobs(db):
    return IngestJobsRepository(
        SimpleNamespace(app=mongo_runtime(), ingest_jobs_collection=db.ingest_jobs)
    )


def write_bundle(db, repository, job, session, record_completion=None):
    """Use fixed synthetic identities to detect any duplicate execution."""
    for name in ("samples", "variants", "cnvs"):
        db[name].insert_one({"_id": job["_id"], "sample_id": job["_id"]}, session=session)
    result = {"sample_id": job["_id"], "status": "created"}
    if record_completion is None:
        repository.complete(job["_id"], job["lease_token"], result, session)
    else:
        record_completion(result, session)
    return result


def runner(db, repository, *, execute=None):
    def ingest(job, record_completion):
        return run_transaction(
            db.client, lambda session: write_bundle(db, repository, job, session, record_completion)
        )

    return IngestJobRunner(
        repository=repository,
        execute=execute or ingest,
        family_enabled=lambda _: True,
        retryable_error=lambda _: True,
        audit=Mock(),
        notify_failure=Mock(),
        cleanup_staging=Mock(),
        lease_seconds=60,
    )


def test_expired_claim_race_has_one_winner_and_fences_old_completion(database):
    db, _, _ = database
    repository = jobs(db)
    job_id = repository.submit(source_payload={}, submitted_by="synthetic")
    previous = repository.claim(job_id, lease_seconds=60)
    db.ingest_jobs.update_one(
        {"_id": job_id},
        {"$set": {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    start = Barrier(2)

    def claim(_):
        start.wait(timeout=10)
        return repository.claim(job_id, lease_seconds=60)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(claim, range(2)))
    winners = [job for job in claimed if job is not None]
    assert len(winners) == 1
    assert winners[0]["lease_token"] != previous["lease_token"]
    with pytest.raises(RuntimeError, match="lease changed"):
        run_transaction(db.client, lambda session: write_bundle(db, repository, previous, session))
    assert db.samples.count_documents({}) == 0
    assert not repository.fail(job_id, previous["lease_token"], retryable=False, error="stale")
    result = run_transaction(
        db.client, lambda session: write_bundle(db, repository, winners[0], session)
    )
    assert repository.get(job_id)["result"] == result
    assert repository.get(job_id)["attempts"] == 2


def test_repeated_submission_and_delivery_keep_one_complete_bundle(database):
    db, _, _ = database
    repository = jobs(db)
    job_id = repository.submit(source_payload={"original": True}, submitted_by="synthetic")
    repository.submit(job_id=job_id, source_payload={"replacement": True}, submitted_by="other")
    assert repository.get(job_id)["source_payload"] == {"original": True}
    executor = runner(db, repository)
    first = executor.run(job_id)
    assert executor.run(job_id) == first
    assert repository.get(job_id)["attempts"] == 1
    assert repository.get(job_id)["source_payload"] is None
    for name in ("samples", "variants", "cnvs"):
        assert db[name].count_documents({}) == 1


def test_unknown_commit_result_retries_commit_without_replaying_writes(database):
    db, commits, _ = database
    repository = jobs(db)
    job_id = repository.submit(source_payload={}, submitted_by="synthetic")
    db.client.admin.command(
        {
            "configureFailPoint": "failCommand",
            "mode": {"times": 1},
            "data": {
                "failCommands": ["commitTransaction"],
                "writeConcernError": {"code": 91, "errmsg": "synthetic lost confirmation"},
                "errorLabels": ["UnknownTransactionCommitResult"],
            },
        }
    )
    result = runner(db, repository).run(job_id)
    assert commits.count >= 2
    assert repository.get(job_id)["result"] == result
    for name in ("samples", "variants", "cnvs"):
        assert db[name].count_documents({}) == 1


def crashing_worker(uri, name, job_id, committed, connection):
    """Pause an owned child while its parent simulates an abrupt process loss."""
    with MongoClient(uri) as client:
        db = client[name]
        repository = jobs(db)
        job = repository.claim(job_id, lease_seconds=60)
        with client.start_session() as session:
            session.start_transaction()
            write_bundle(db, repository, job, session)
            if committed:
                session.commit_transaction()
            connection.send(session.session_id)
            connection.recv()


@pytest.mark.parametrize("committed", [False, True], ids=["before-commit", "after-commit"])
def test_worker_process_loss_preserves_bundle_and_recovers_delivery(database, committed):
    db, _, uri = database
    repository = jobs(db)
    job_id = repository.submit(source_payload={}, submitted_by="synthetic")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=crashing_worker, args=(uri, db.name, job_id, committed, child))
    process.start()
    child.close()
    try:
        assert parent.poll(25), "Disposable worker did not reach the crash point"
        session_id = parent.recv()
        process.kill()
        process.join(timeout=10)
        assert not process.is_alive()
        for name in ("samples", "variants", "cnvs"):
            assert db[name].count_documents({}) == int(committed)
        # Reap only the killed child's session, without waiting for MongoDB's timeout.
        db.client.admin.command({"killSessions": [session_id]})
        if not committed:
            db.ingest_jobs.update_one(
                {"_id": job_id},
                {"$set": {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}},
            )
        recovered = runner(db, repository).run(job_id)
        assert repository.get(job_id)["result"] == recovered
        assert repository.get(job_id)["attempts"] == (1 if committed else 2)
        for name in ("samples", "variants", "cnvs"):
            assert db[name].count_documents({}) == 1
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        parent.close()
