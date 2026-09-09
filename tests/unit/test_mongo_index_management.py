"""Tests for explicit MongoDB index planning and retirement."""

from types import SimpleNamespace

import pytest

from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.mongo.index_management import build_index_plan, retire_index


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
