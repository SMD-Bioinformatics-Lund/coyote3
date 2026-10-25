#!/usr/bin/env python3
"""Run backend checks against newly created loopback-only disposable MongoDB replicas."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import PyMongoError

ROOT = Path(__file__).resolve().parents[2]
URI_KEYS = (
    "AUDIT_TEST_MONGO_URI",
    "LIFECYCLE_TEST_MONGO_URI",
    "REPORT_TEST_MONGO_URI",
    "QUERY_RULE_TEST_MONGO_URI",
    "ASSAY_SETUP_TEST_MONGO_URI",
    "CATALOG_TEST_MONGO_URI",
    "NOTIFICATION_TEST_MONGO_URI",
    "MONGO_TOPOLOGY_TEST_URI",
    "BOOTSTRAP_TEST_MONGO_URI",
    "CLINICAL_RULE_TEST_MONGO_URI",
)


def start_replica(directory: Path, name: str, processes: list[subprocess.Popen]) -> str:
    """Start one owned MongoDB process and wait for its single-member replica election.

    Args:
        directory: New temporary data and log directory.
        name: Unique replica-set name used only for this validation run.
        processes: Owned child processes to terminate even when startup fails.

    Returns:
        Loopback URI for the newly created replica set.

    Raises:
        RuntimeError: MongoDB exits or cannot become writable before the deadline.
    """
    directory.mkdir()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [
            "mongod",
            "--dbpath",
            str(directory),
            "--port",
            str(port),
            "--bind_ip",
            "127.0.0.1",
            "--replSet",
            name,
            "--logpath",
            str(directory / "mongod.log"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    processes.append(process)
    client = MongoClient(
        f"mongodb://127.0.0.1:{port}/?directConnection=true", serverSelectionTimeoutMS=500
    )
    deadline = time.monotonic() + 45
    initialized = False
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Disposable MongoDB exited; inspect {directory / 'mongod.log'}")
            try:
                if not initialized:
                    client.admin.command(
                        "replSetInitiate",
                        {"_id": name, "members": [{"_id": 0, "host": f"127.0.0.1:{port}"}]},
                    )
                    initialized = True
                if client.admin.command("hello").get("isWritablePrimary"):
                    return f"mongodb://127.0.0.1:{port}/?replicaSet={name}"
            except PyMongoError:
                pass
            time.sleep(0.2)
    finally:
        client.close()
    raise RuntimeError("Disposable MongoDB did not become writable within 45 seconds")


def main() -> None:
    """Run pytest with isolated endpoints and clean up only this runner's child processes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if shutil.which("mongod") is None:
        parser.error("mongod must be installed; this runner never connects to existing databases")
    processes: list[subprocess.Popen] = []
    with tempfile.TemporaryDirectory(prefix="coyote3-transaction-tests-") as temporary:
        try:
            prefix = "coyote-validation-" + uuid4().hex[:10]
            primary = start_replica(Path(temporary) / "primary", prefix + "-primary", processes)
            destination = start_replica(
                Path(temporary) / "destination", prefix + "-destination", processes
            )
            environment = {**os.environ, **dict.fromkeys(URI_KEYS, primary)}
            environment.update(
                AUDIT_TEST_DEST_URI=destination,
                MONGO_TOPOLOGY_TEST_KB_URI=destination,
                ENV_NAME="test",
                TESTING="1",
                DEVELOPMENT="0",
                PYTHONPATH=str(ROOT),
                COYOTE3_MONGO_URI=primary,
                IDENTITY_MONGO_URI=primary,
                KNOWLEDGEBASE_MONGO_URI=destination,
                BAM_MONGO_URI=primary,
                COYOTE3_DB="coyote3_disposable_app",
                IDENTITY_DB="coyote3_disposable_identity",
                KNOWLEDGEBASE_DB="coyote3_disposable_kb",
                BAM_DB="coyote3_disposable_bam",
            )
            arguments = args.pytest_args
            if arguments[:1] == ["--"]:
                arguments = arguments[1:]
            arguments = arguments or ["-q", "tests/integration", "--tb=short"]
            result = subprocess.run(
                [sys.executable, "-m", "pytest", *arguments], cwd=ROOT, env=environment
            )
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
