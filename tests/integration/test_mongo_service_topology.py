"""Opt-in namespace routing against disposable MongoDB databases only."""

import os
from uuid import uuid4

import pytest

from api.infra.mongo.connections import MongoConnections


def test_configured_services_write_only_to_their_own_database():
    uri = os.getenv("MONGO_TOPOLOGY_TEST_URI")
    if not uri:
        pytest.skip("Set MONGO_TOPOLOGY_TEST_URI for disposable service-routing tests")
    prefix = f"coyote3_topology_test_{uuid4().hex}_"
    pool = MongoConnections(
        {
            "ENV_NAME": "testing",
            "COYOTE3_MONGO_URI": uri,
            "KNOWLEDGEBASE_MONGO_URI": os.getenv("MONGO_TOPOLOGY_TEST_KB_URI") or uri,
            "COYOTE3_DB": prefix + "app",
            "IDENTITY_DB": prefix + "identity",
            "KNOWLEDGEBASE_DB": prefix + "kb",
            "BAM_DB": prefix + "bam",
            "MONGO_SERVER_SELECTION_TIMEOUT_MS": 3000,
        }
    )
    try:
        pool.ping()
        for service, database in pool.databases.items():
            database.routing_probe.insert_one({"_id": service, "synthetic": True})
        for service, database in pool.databases.items():
            assert list(database.routing_probe.find({}, {"_id": 1})) == [{"_id": service}]
        assert pool.databases["primary"].client is pool.databases["identity"].client
    finally:
        try:
            for database in pool.databases.values():
                assert database.name.startswith(prefix)
                database.client.drop_database(database.name)
        finally:
            pool.close()
