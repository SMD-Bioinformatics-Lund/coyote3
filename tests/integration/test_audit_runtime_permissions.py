"""Enforce audit permissions on an owned, authentication-enabled disposable replica set."""

import logging
import shutil
import subprocess
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError
from pymongo.uri_parser import parse_uri

from api.infra.mongo.repositories.audit_integrity import append_event, verify_chain
from api.infra.security.indexes import ensure_security_indexes
from api.infra.security.mongo_roles import (
    IDENTITY_ROLE,
    provision_identity,
    verify_runtime_audit_permissions,
)
from scripts.quality.run_transaction_tests import start_replica


@pytest.fixture(scope="module")
def authenticated_replica(tmp_path_factory):
    """Start a fresh replica, provision users, and restart it with authorization enabled."""
    if shutil.which("mongod") is None:
        pytest.skip("mongod is required for the isolated database-permission test")
    root = tmp_path_factory.mktemp("audit-auth")
    directory = root / "mongo"
    name = "audit-auth-" + uuid4().hex[:8]
    processes = []
    runtime = None
    try:
        uri = start_replica(directory, name, processes)
        password = uuid4().hex
        with MongoClient(uri) as client:
            client.admin.command(
                "createUser",
                "synthetic-root",
                pwd=uuid4().hex,
                roles=[{"role": "root", "db": "admin"}],
            )
            provision_identity(client.synthetic_identity)
            client.admin.command(
                "createUser",
                "synthetic-runtime",
                pwd=password,
                roles=[
                    {"role": IDENTITY_ROLE, "db": "synthetic_identity"},
                    {"role": "readWrite", "db": "synthetic_app"},
                ],
            )
        with MongoClient(
            uri, username="synthetic-runtime", password=password, authSource="admin"
        ) as unprotected:
            verify_runtime_audit_permissions(unprotected, "synthetic_identity")
        processes[0].terminate()
        processes[0].wait(timeout=15)
        keyfile = root / "keyfile"
        keyfile.write_text(uuid4().hex + uuid4().hex)
        keyfile.chmod(0o600)
        port = parse_uri(uri)["nodelist"][0][1]
        processes.append(
            subprocess.Popen(
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
                    "--auth",
                    "--keyFile",
                    str(keyfile),
                    "--logpath",
                    str(directory / "authenticated.log"),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        runtime = MongoClient(
            uri,
            username="synthetic-runtime",
            password=password,
            authSource="admin",
            serverSelectionTimeoutMS=500,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if runtime.admin.command("hello").get("isWritablePrimary"):
                    break
            except PyMongoError:
                pass
            time.sleep(0.2)
        else:
            pytest.fail("Owned authentication-enabled replica did not become ready")
        yield runtime
    finally:
        if runtime is not None:
            runtime.close()
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)


def test_runtime_can_append_verify_and_clean_operational_events_but_cannot_change_audit_history(
    authenticated_replica,
):
    client = authenticated_replica
    identity = client.synthetic_identity
    verify_runtime_audit_permissions(client, identity.name)
    event = {
        "_id": ObjectId(),
        "retention_class": "traceability",
        "occurred_at": datetime.now(timezone.utc),
        "source": {"environment": "test"},
        "message": "Synthetic clinical change",
    }
    append_event(identity.audit_events, event)
    assert verify_chain(identity.audit_events)["valid"]
    operational = {
        "_id": ObjectId(),
        "retention_class": "operational",
        "message": "Synthetic request",
    }
    append_event(identity.operational_audit_events, operational)
    append_event(identity.operational_audit_events, {**operational, "message": "Cannot replace"})
    assert identity.operational_audit_events.find_one()["message"] == "Synthetic request"
    assert (
        identity.operational_audit_events.delete_one({"_id": operational["_id"]}).deleted_count == 1
    )
    for operation in (
        lambda: identity.audit_events.update_one(
            {"_id": event["_id"]}, {"$set": {"message": "Tampered"}}
        ),
        lambda: identity.audit_events.delete_one({"_id": event["_id"]}),
        lambda: identity.audit_events.drop(),
        lambda: identity.audit_events.create_index("occurred_at", expireAfterSeconds=0),
        lambda: identity.command("collMod", "audit_events", validator={}),
    ):
        with pytest.raises(OperationFailure) as failure:
            operation()
        assert failure.value.code == 13
    ensure_security_indexes(
        primary_db=client.synthetic_app,
        identity_db=identity,
        config={},
        logger=logging.getLogger(__name__),
    )
    assert verify_chain(identity.audit_events)["valid"]
