"""Tests for explicit MongoDB index planning and retirement."""

import logging
from types import SimpleNamespace

import mongomock
import pytest

from api.config.loaders.collections import load_collection_mapping
from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.mongo.index_management import build_index_plan, retire_index
from api.infra.mongo.repositories.assay_setup import AssaySetupRepository
from api.infra.mongo.repositories.query_rules import QueryRuleRepository
from api.infra.mongo.runtime_adapter import MongoAdapter
from api.infra.security.indexes import ensure_security_indexes


class FakeCollection:
    def __init__(self, name: str, indexes: list[dict]):
        self.name = name
        self.indexes = indexes
        self.dropped: list[str] = []

    def list_indexes(self):
        return list(self.indexes)

    def drop_index(self, name: str):
        self.dropped.append(name)


class FakeRepository:
    def __init__(self, collection: FakeCollection):
        self.collection = collection

    def get_collection(self):
        return self.collection

    def set_collection(self, collection):
        self.collection = collection

    def ensure_indexes(self):
        self.collection.create_index([("sample_id", 1)], name="sample_id_1", unique=True)
        self.collection.create_index([("updated_on", -1)], name="updated_on_desc_1")


class FakeDatabase(dict):
    """Expose a collection inventory without any database write methods."""

    def __missing__(self, name):
        self[name] = FakeCollection(name, [])
        return self[name]

    def list_collection_names(self):
        return list(self)


def adapter_for(repository: FakeRepository):
    security_collections = {
        "api_sessions": FakeCollection("api_sessions", []),
        "audit_events": FakeCollection("audit_events", []),
        "app_controls": FakeCollection("app_controls", []),
    }
    primary_database = type(
        "FakeDatabase", (), {"__getitem__": lambda self, key: security_collections[key]}
    )()
    identity_database = type(
        "FakeIdentityDatabase", (), {"__getitem__": lambda self, key: security_collections[key]}
    )()
    return SimpleNamespace(
        iter_repositories=lambda: iter([("samples", repository)]),
        app=SimpleNamespace(config={}),
        coyote_db=primary_database,
        identity_db=identity_database,
    )


def test_index_plan_reports_present_and_missing_contracts():
    collection = FakeCollection(
        "samples", [{"name": "sample_id_1", "key": {"sample_id": 1}, "unique": True}]
    )
    plan = build_index_plan(adapter_for(FakeRepository(collection)))

    assert [(entry["name"], entry["state"]) for entry in plan[:2]] == [
        ("sample_id_1", "present"),
        ("updated_on_desc_1", "missing"),
    ]
    assert "ttl_api_session_expiry" in {entry["name"] for entry in plan}


def test_index_plan_reports_option_conflicts():
    collection = FakeCollection(
        "samples",
        [{"name": "sample_id_1", "key": {"sample_id": 1}, "unique": False}],
    )

    plan = build_index_plan(adapter_for(FakeRepository(collection)))

    assert plan[0]["state"] == "conflict"


@pytest.mark.parametrize("existing", [False, True])
def test_assay_setup_index_plan_is_read_only(existing):
    """Inspect assay setup reservations through the API startup index recorder."""
    indexes = [
        {"name": "setup_assay_unique", "key": {"asp_id": 1}, "unique": True},
        {"name": "setup_status_updated", "key": {"status": 1, "updated_at": -1}},
    ]
    collection = FakeCollection("assay_setups", indexes if existing else [])
    repository = AssaySetupRepository(SimpleNamespace(assay_setups_collection=collection))

    # No create_index method on FakeCollection: inspection must never write indexes.
    plan = build_index_plan(adapter_for(repository))

    assert [(item["name"], item["keys"], item["state"]) for item in plan[:2]] == [
        ("setup_assay_unique", (("asp_id", 1),), "present" if existing else "missing"),
        (
            "setup_status_updated",
            (("status", 1), ("updated_at", -1)),
            "present" if existing else "missing",
        ),
    ]
    assert plan[0]["options"] == {"unique": True}
    assert repository.get_collection() is collection


@pytest.mark.parametrize("existing", [False, True])
def test_query_rule_index_plan_preserves_existing_index_names(existing):
    """Inspect all query-rule indexes without writes or renaming deployed indexes."""
    import mongomock

    collection = mongomock.MongoClient().application.query_rule_sets
    repository = QueryRuleRepository(
        SimpleNamespace(
            query_rule_sets_collection=collection,
            query_rule_revisions_collection=collection.database.query_rule_revisions,
        )
    )
    repository.ensure_indexes()
    indexes = list(collection.list_indexes())
    readonly = FakeCollection("query_rule_sets", indexes if existing else [])
    repository.set_collection(readonly)

    plan = build_index_plan(adapter_for(repository))

    assert [(item["name"], item["state"]) for item in plan[:3]] == [
        ("query_rule_scope_version", "present" if existing else "missing"),
        ("query_rule_published_scope", "present" if existing else "missing"),
        (
            "status_1_scope.assay_group_1_scope.analysis_1_scope.intent_1",
            "present" if existing else "missing",
        ),
    ]
    assert repository.get_collection() is readonly


def test_all_registered_repository_indexes_can_be_planned_without_writes():
    """Cover the complete installation plan using collections that cannot create indexes."""
    mapping = load_collection_mapping()
    adapter = MongoAdapter()
    adapter.app = SimpleNamespace(config={"DB_COLLECTIONS_CONFIG": mapping})
    for service, attribute in (
        ("primary", "coyote_db"),
        ("identity", "identity_db"),
        ("knowledgebase", "knowledgebase_db"),
        ("bam", "bam_db"),
    ):
        setattr(
            adapter,
            attribute,
            FakeDatabase({name: FakeCollection(name, []) for name in mapping[service].values()}),
        )
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)

    plan = build_index_plan(adapter)

    assert plan
    assert all(item["state"] == "missing" for item in plan)
    assert "query_rule_scope_version" in {item["name"] for item in plan}


def test_full_index_installation_and_rerun_preserve_records():
    """Install every repository/security index twice on an isolated in-memory database."""
    adapter = MongoAdapter()
    adapter.app = SimpleNamespace(
        config={"DB_COLLECTIONS_CONFIG": load_collection_mapping()},
        logger=logging.getLogger("test.index_installation"),
    )
    client = mongomock.MongoClient()
    for attribute in ("coyote_db", "identity_db", "knowledgebase_db", "bam_db"):
        setattr(adapter, attribute, client[attribute])
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    adapter.brcaexchange_collection.insert_one({"id": "synthetic", "chr": "17", "pos": 1})
    # Existing reference releases need not contain GRCh38 coordinates.
    adapter.brcaexchange_collection.create_index(
        [("chr38", 1), ("pos38", 1), ("ref38", 1), ("alt38", 1)],
        name="chr38_pos38_ref38_alt38",
        sparse=True,
    )
    before = list(adapter.brcaexchange_collection.find())
    assert not any(item["state"] == "conflict" for item in build_index_plan(adapter))
    for _ in range(2):
        adapter.ensure_repository_indexes()
        ensure_security_indexes(
            primary_db=adapter.coyote_db,
            identity_db=adapter.identity_db,
            config=adapter.app.config,
            logger=adapter.app.logger,
        )
        plan = build_index_plan(adapter)
        assert all(item["state"] == "present" for item in plan), [
            item for item in plan if item["state"] != "present"
        ]
        assert list(adapter.brcaexchange_collection.find()) == before


@pytest.mark.parametrize("state, expected", [("present", 0), ("missing", 1), ("conflict", 1)])
def test_index_apply_summary_reports_incomplete_indexes(monkeypatch, capsys, state, expected):
    """Do not report a successful installation when index creation was suppressed."""
    from unittest.mock import Mock

    from scripts.database import manage_mongo_indexes

    adapter = Mock()
    monkeypatch.setattr(manage_mongo_indexes, "_adapter", lambda scope: adapter)
    monkeypatch.setattr(
        manage_mongo_indexes, "build_index_plan", lambda _, **kwargs: [{"state": state}]
    )
    monkeypatch.setattr(manage_mongo_indexes, "ensure_security_indexes", Mock())
    monkeypatch.setattr("sys.argv", ["manage_mongo_indexes.py", "apply", "--summary"])

    assert manage_mongo_indexes.main() == expected
    assert f"{state}=1" in capsys.readouterr().out
    adapter.ensure_repository_indexes.assert_called_once()


@pytest.mark.parametrize("scope", ["application", "knowledgebase", "all"])
def test_standalone_index_scope_isolates_database_writes(monkeypatch, scope):
    """Exercise the real CLI and repository registry against isolated synthetic databases."""
    from scripts.database import manage_mongo_indexes

    client = mongomock.MongoClient()

    def connect(adapter, app):
        adapter.app = app
        for attribute in ("coyote_db", "identity_db", "knowledgebase_db", "bam_db"):
            setattr(adapter, attribute, client[attribute])

    monkeypatch.setattr(MongoAdapter, "connect", connect)
    monkeypatch.setattr(
        manage_mongo_indexes,
        "_config",
        lambda: SimpleNamespace(DB_COLLECTIONS_CONFIG=load_collection_mapping()),
    )
    monkeypatch.setattr(
        "sys.argv", ["manage_mongo_indexes.py", "apply", "--summary", "--scope", scope]
    )
    assert manage_mongo_indexes.main() == 0
    assert bool(client.knowledgebase_db.list_collection_names()) == (scope != "application")
    for name in ("coyote_db", "identity_db", "bam_db"):
        assert bool(client[name].list_collection_names()) == (scope != "knowledgebase")


def test_oncokb_index_plan_only_reads_all_three_collections():
    collections = SimpleNamespace(
        oncokb_public_collection=FakeCollection("oncokb_public", []),
        oncokb_genes_public_collection=FakeCollection("oncokb_genes_public", []),
        oncokb_cancer_genes_public_collection=FakeCollection("oncokb_cancer_genes_public", []),
    )
    repository = OncoKbPublicCacheRepository(collections)
    # FakeCollection deliberately has no create_index: any database write fails.
    plan = build_index_plan(adapter_for(repository))
    assert {item["collection"] for item in plan if item["repository"] == "samples"} == {
        "oncokb_public",
        "oncokb_genes_public",
        "oncokb_cancer_genes_public",
    }
    assert repository.adapter is collections
    assert repository.get_collection() is collections.oncokb_public_collection
    assert all(item["state"] == "missing" for item in plan)


def test_retire_index_requires_a_known_collection_and_exact_existing_name():
    collection = FakeCollection("samples", [{"name": "legacy_1", "key": {"legacy": 1}}])
    adapter = adapter_for(FakeRepository(collection))

    retire_index(adapter, collection_name="samples", index_name="legacy_1")
    assert collection.dropped == ["legacy_1"]

    with pytest.raises(ValueError, match="cannot be retired"):
        retire_index(adapter, collection_name="samples", index_name="_id_")
    with pytest.raises(ValueError, match="Unknown managed collection"):
        retire_index(adapter, collection_name="other", index_name="legacy_1")
    with pytest.raises(ValueError, match="does not exist"):
        retire_index(adapter, collection_name="samples", index_name="missing_1")


def test_index_retirement_rejects_ambiguous_cross_service_collection_names():
    app = FakeCollection("samples", [{"name": "legacy_1", "key": {"legacy": 1}}])
    bam = FakeCollection("samples", [{"name": "legacy_1", "key": {"legacy": 1}}])
    adapter = SimpleNamespace(
        iter_repositories=lambda: iter(
            [
                ("samples", FakeRepository(app)),
                ("bam", FakeRepository(bam)),
            ]
        )
    )
    with pytest.raises(ValueError, match="ambiguous"):
        retire_index(adapter, collection_name="samples", index_name="legacy_1")
    assert app.dropped == bam.dropped == []
    retire_index(adapter, collection_name="samples", index_name="legacy_1", repository_name="bam")
    assert app.dropped == []
    assert bam.dropped == ["legacy_1"]
