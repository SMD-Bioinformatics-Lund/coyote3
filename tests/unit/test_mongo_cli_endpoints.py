"""Maintenance endpoint selection must not accidentally write to the app server."""

import argparse
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest

from api.config.paths import COLLECTIONS_CONFIG_PATH
from scripts import migrate_identity_database, migrate_knowledgebase_database
from scripts.knowledgebase_update_common import add_common_arguments
from scripts.migrate_knowledgebase_database import assert_distinct_databases


@pytest.mark.parametrize(
    "target_hosts,allowed",
    [
        (["source:27017"], False),
        (["source:27017", "new-member:27017"], False),
        (["target:27017"], True),
    ],
)
def test_same_name_migration_verifies_physical_replica_set_identity(target_hosts, allowed):
    source = SimpleNamespace(name="knowledgebases", client=Mock())
    target = SimpleNamespace(name="knowledgebases", client=Mock())
    source.client.admin.command.return_value = {"setName": "rs", "hosts": ["source:27017"]}
    target.client.admin.command.return_value = {"setName": "rs", "hosts": target_hosts}
    if allowed:
        assert_distinct_databases(source, target)
    else:
        with pytest.raises(ValueError, match="different database namespaces"):
            assert_distinct_databases(source, target)


def test_same_name_migration_fails_closed_for_unverifiable_cluster_identity():
    source = SimpleNamespace(name="knowledgebases", client=Mock())
    target = SimpleNamespace(name="knowledgebases", client=Mock())
    source.client.admin.command.return_value = {"msg": "isdbgrid"}
    with pytest.raises(ValueError, match="Cannot prove"):
        assert_distinct_databases(source, target)


@pytest.mark.parametrize(
    "module,target_key",
    [
        (migrate_identity_database, "IDENTITY_MONGO_URI"),
        (migrate_knowledgebase_database, "KNOWLEDGEBASE_MONGO_URI"),
    ],
)
@pytest.mark.parametrize("shared", [False, True])
def test_migration_targets_independent_endpoints_or_explicit_shared_uri(
    monkeypatch, module, target_key, shared
):
    monkeypatch.setenv("COYOTE3_MONGO_URI", "mongodb://source:27017")
    monkeypatch.setenv(target_key, "mongodb://target:27017")
    source = mongomock.MongoClient()
    target = mongomock.MongoClient()
    factory = Mock(side_effect=[source, target])
    monkeypatch.setattr(module, "MongoClient", factory)
    result = module.run(
        SimpleNamespace(
            mongo_uri="mongodb://shared:27017" if shared else "",
            source_mongo_uri="",
            target_mongo_uri="",
            source_db="synthetic_source",
            target_db="synthetic_target",
            collections_config=COLLECTIONS_CONFIG_PATH,
            apply=False,
            drop_source=False,
            confirm_drop_source="",
        )
    )
    assert result["mode"] == "dry-run"
    assert source.synthetic_source.list_collection_names() == []
    assert target.synthetic_target.list_collection_names() == []
    uris = [call.args[0] for call in factory.call_args_list]
    assert uris == (
        ["mongodb://shared:27017"]
        if shared
        else ["mongodb://source:27017", "mongodb://target:27017"]
    )


def test_importer_prefers_knowledgebase_uri_over_primary_and_legacy(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://legacy:27017")
    monkeypatch.setenv("COYOTE3_MONGO_URI", "mongodb://app:27017")
    monkeypatch.setenv("KNOWLEDGEBASE_MONGO_URI", "mongodb://kb:27017")
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    assert parser.parse_args(["--release", "synthetic"]).mongo_uri == "mongodb://kb:27017"
    assert (
        parser.parse_args(
            ["--release", "synthetic", "--mongo-uri", "mongodb://maintenance:27017"]
        ).mongo_uri
        == "mongodb://maintenance:27017"
    )
