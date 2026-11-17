"""Exercise the shipped recovery commands against disposable local MongoDB replicas."""

import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from bson import ObjectId
from coyote_mongo.repositories.audit_integrity import append_event, verify_chain
from pymongo import MongoClient

from scripts.quality.run_transaction_tests import start_replica

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def recovery_targets(tmp_path):
    """Use owned replicas and cached tools on the local Docker socket only."""
    if os.getenv("COYOTE4_RUN_DISPOSABLE_TESTS") != "1":
        pytest.skip("Use run_transaction_tests.py for disposable backup and restore checks")
    if not shutil.which("mongod") or not shutil.which("docker"):
        pytest.skip("Local mongod and Docker are required for recovery checks")
    environment = {key: value for key, value in os.environ.items() if key != "DOCKER_CONTEXT"}
    environment["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    image = subprocess.run(
        ["docker", "--host", environment["DOCKER_HOST"], "image", "inspect", "mongo:8.2"],
        env=environment,
        capture_output=True,
        timeout=10,
    )
    if image.returncode:
        pytest.skip("The local Mongo tools image is unavailable; no images are pulled")
    processes = []
    try:
        prefix = "recovery-test-" + uuid4().hex[:8]
        source = start_replica(tmp_path / "source", prefix + "-source", processes)
        target = start_replica(tmp_path / "target", prefix + "-target", processes)
        yield source, target, environment
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def test_private_backup_restores_reports_indexes_and_audit_chain(recovery_targets, tmp_path):
    """An operator-owned archive must restore report evidence and audit integrity intact."""
    source_uri, target_uri, environment = recovery_targets
    archives = tmp_path / "archives"
    archives.mkdir(mode=0o700)
    with MongoClient(source_uri) as source, MongoClient(target_uri) as target:
        app = source.coyote4_recovery_test
        identity = source.coyote4_recovery_test_identity
        sample_id, report_id = ObjectId(), ObjectId()
        app.samples.insert_one(
            {"_id": sample_id, "name": "SYNTHETIC", "latest_report_id": report_id}
        )
        app.reports.insert_one(
            {
                "_id": report_id,
                "sample_id": sample_id,
                "report_id": "synthetic-report",
                "snapshot_rows": [{"gene": "TP53", "tier": 1, "allele_fraction": 0.23}],
            }
        )
        app.reports.create_index("report_id", unique=True)
        append_event(
            identity.audit_events,
            {
                "_id": ObjectId(),
                "occurred_at": datetime.now(timezone.utc),
                "retention_class": "traceability",
                "source": {"environment": "test"},
                "message": "Synthetic report issued",
            },
        )
        backup = subprocess.run(
            [
                "bash",
                "scripts/database/mongo_backup_archive.sh",
                "--mongo-uri",
                source_uri,
                "--out-dir",
                str(archives),
                "--docker-network",
                "host",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert backup.returncode == 0, backup.stdout + backup.stderr
        (archive,) = archives.glob("*.archive.gz")
        assert archive.stat().st_uid == os.getuid()
        archive.chmod(0o600)
        metadata = dict(
            line.split("=", 1) for line in Path(str(archive) + ".meta").read_text().splitlines()
        )
        assert metadata["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
        restore = subprocess.run(
            [
                "bash",
                "scripts/database/mongo_restore_archive.sh",
                "--mongo-uri",
                target_uri,
                "--archive",
                str(archive),
                "--docker-network",
                "host",
                "--confirm",
                "RESTORE_PATIENT_DATA",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert restore.returncode == 0, restore.stdout + restore.stderr
        for database in (app.name, identity.name):
            names = source[database].list_collection_names()
            assert set(target[database].list_collection_names()) == set(names)
            for name in names:
                before, after = source[database][name], target[database][name]
                assert list(after.find().sort("_id")) == list(before.find().sort("_id"))
                assert list(after.list_indexes()) == list(before.list_indexes())
        assert verify_chain(target[identity.name].audit_events)["valid"]
