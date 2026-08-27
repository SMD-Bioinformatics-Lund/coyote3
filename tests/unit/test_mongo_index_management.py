"""Tests for explicit MongoDB index planning and retirement."""

from types import SimpleNamespace

import pytest

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
    database = type(
        "FakeDatabase", (), {"__getitem__": lambda self, key: security_collections[key]}
    )()
    return SimpleNamespace(
        iter_repositories=lambda: iter([("samples", repository)]),
        app=SimpleNamespace(config={}),
        coyote_db=database,
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
