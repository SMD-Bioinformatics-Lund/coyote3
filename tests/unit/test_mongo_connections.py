"""Independent endpoint selection without network access or clinical records."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pymongo import MongoClient

from api.config.loaders.collections import load_collection_mapping
from api.config.mongo import mongo_endpoints, mongo_uri
from api.infra.mongo.connections import MongoConnections
from api.infra.mongo.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.runtime_adapter import MongoAdapter


def config(**overrides):
    return {
        "ENV_NAME": "development",
        "COYOTE3_MONGO_URI": "mongodb://configured-mongo:27017/?replicaSet=coyote3-rs",
        "COYOTE3_DB": "app_dev",
        "IDENTITY_DB": "identity_dev",
        "KNOWLEDGEBASE_DB": "knowledgebases",
        "BAM_DB": "bam_dev",
        "DB_COLLECTIONS_CONFIG": load_collection_mapping(),
        **overrides,
    }


@pytest.fixture
def connections():
    opened = []

    def factory(**overrides):
        pool = MongoConnections(
            config(**overrides),
            client_factory=lambda uri, **options: MongoClient(uri, connect=False, **options),
        )
        opened.append(pool)
        return pool

    yield factory
    for pool in opened:
        pool.close()


def test_one_instance_reuses_client_for_distinct_logical_databases(connections):
    pool = connections()
    assert len({id(db.client) for db in pool.databases.values()}) == 1
    assert {db.name for db in pool.databases.values()} == {
        "app_dev",
        "identity_dev",
        "knowledgebases",
        "bam_dev",
    }
    assert pool.databases["primary"].client.options.replica_set_name == "coyote3-rs"


def test_split_instances_and_replica_set_names(connections):
    pool = connections(
        COYOTE3_MONGO_URI="mongodb://mongo-app:27017/?replicaSet=app-rs",
        IDENTITY_MONGO_URI="mongodb://mongo-identity:27017/?replicaSet=identity-rs",
        KNOWLEDGEBASE_MONGO_URI="mongodb://mongo-kb:27017/?replicaSet=kb-rs",
    )
    assert len({id(db.client) for db in pool.databases.values()}) == 3
    assert pool.databases["bam"].client is pool.databases["primary"].client
    for service, name in [
        ("primary", "app-rs"),
        ("identity", "identity-rs"),
        ("knowledgebase", "kb-rs"),
    ]:
        assert pool.databases[service].client.options.replica_set_name == name


def test_same_database_name_on_separate_endpoints_keeps_logical_mapping(connections):
    pool = connections(
        IDENTITY_DB="app_dev",
        KNOWLEDGEBASE_DB="app_dev",
        IDENTITY_MONGO_URI="mongodb://identity:27017/?replicaSet=identity-rs",
        KNOWLEDGEBASE_MONGO_URI="mongodb://kb:27017/?replicaSet=kb-rs",
    )
    adapter = MongoAdapter()
    adapter.app = SimpleNamespace(config=config())
    adapter.coyote_db = pool.databases["primary"]
    adapter.identity_db = pool.databases["identity"]
    adapter.knowledgebase_db = pool.databases["knowledgebase"]
    adapter.bam_db = pool.databases["bam"]
    adapter.setup()
    assert adapter.users_collection.database.client is pool.databases["identity"].client
    assert (
        adapter.civic_variants_collection.database.client is pool.databases["knowledgebase"].client
    )
    assert adapter.samples_collection.database.client is pool.databases["primary"].client


def test_database_selection_does_not_rewrite_uri_path_or_auth_source(connections):
    uri = (
        "mongodb://user:synthetic@mongo-app:27017/authentication?authSource=admin&replicaSet=app-rs"
    )
    pool = connections(COYOTE3_MONGO_URI=uri)
    assert pool.endpoints["primary"].uri == uri
    assert pool.databases["primary"].name == "app_dev"
    assert "synthetic" not in repr(pool.endpoints)


def test_explicit_uri_precedence_and_legacy_fallback():
    legacy = "mongodb://legacy:27017/?replicaSet=legacy-rs"
    explicit = "mongodb://explicit:27017/?replicaSet=other-rs"
    assert mongo_uri(config(COYOTE3_MONGO_URI="", MONGO_URI=legacy), "identity") == legacy
    assert mongo_uri(config(MONGO_URI=legacy, COYOTE3_MONGO_URI=explicit), "identity") == explicit


@pytest.mark.parametrize("uri", ["", "https://mongo.invalid", "mongodb://"])
@pytest.mark.parametrize("environment", ["development", "test", "staging", "production"])
def test_every_environment_requires_valid_endpoint(uri, environment):
    with pytest.raises(RuntimeError, match="COYOTE3_MONGO_URI"):
        mongo_endpoints(config(ENV_NAME=environment, COYOTE3_MONGO_URI=uri))


def test_same_endpoint_and_database_cannot_mix_logical_services():
    with pytest.raises(RuntimeError, match="must be different"):
        mongo_endpoints(config(IDENTITY_DB="app_dev"))


def test_different_credentials_do_not_allow_namespace_collision():
    with pytest.raises(RuntimeError, match="must be different"):
        mongo_endpoints(
            config(
                IDENTITY_DB="app_dev",
                COYOTE3_MONGO_URI="mongodb://one:synthetic@mongo:27017/admin?replicaSet=rs",
                IDENTITY_MONGO_URI="mongodb://two:synthetic@mongo:27017/identity?replicaSet=rs",
            )
        )


def test_reused_client_is_pinged_and_closed_only_once():
    client = Mock()
    factory = Mock(return_value=client)
    pool = MongoConnections(config(), client_factory=factory)
    pool.ping()
    pool.close()
    pool.close()
    factory.assert_called_once()
    client.admin.command.assert_called_once_with("ping")
    client.close.assert_called_once()


def test_initialization_failure_closes_existing_clients():
    client = Mock()
    factory = Mock(side_effect=[client, ValueError("invalid configuration")])
    with pytest.raises(ValueError):
        MongoConnections(
            config(KNOWLEDGEBASE_MONGO_URI="mongodb://kb:27017"), client_factory=factory
        )
    client.close.assert_called_once()


def test_remote_collection_rejects_async_receipt_before_writing(connections):
    pool = connections(KNOWLEDGEBASE_MONGO_URI="mongodb://kb:27017/?replicaSet=kb-rs")
    gateway = IngestCollectionGateway(
        collections={
            "samples": pool.databases["primary"].samples,
            "civic_variants": pool.databases["knowledgebase"].civic_variants,
        }
    )
    gateway.validate_completion_target("samples")
    with pytest.raises(ValueError, match="synchronous ingestion"):
        gateway.insert_documents("civic_variants", [], record_completion=Mock())


def test_target_specific_transaction_uses_target_client(connections, monkeypatch):
    pool = connections(IDENTITY_MONGO_URI="mongodb://identity:27017/?replicaSet=identity-rs")
    gateway = IngestCollectionGateway(
        collections={
            "samples": pool.databases["primary"].samples,
            "users": pool.databases["identity"].users,
        }
    )
    execute = Mock(return_value="committed")
    monkeypatch.setattr("api.infra.mongo.ingest_gateway.run_transaction", execute)
    operation = Mock()
    assert gateway.run_collection_transaction("users", operation) == "committed"
    execute.assert_called_once_with(pool.databases["identity"].client, operation)
