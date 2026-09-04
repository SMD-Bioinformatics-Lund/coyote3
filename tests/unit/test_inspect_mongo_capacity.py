"""Tests for the read-only Mongo capacity snapshot command."""

from types import SimpleNamespace

from scripts.inspect_mongo_capacity import collection_snapshot, snapshot


class FakeDatabase:
    name = "coyote3_test"

    def command(self, command: str, collection_name: str):
        assert command == "collStats"
        return {"storageSize": 20, "size": 12, "totalIndexSize": 8}


class FakeCollection:
    name = "variants"
    database = FakeDatabase()

    def estimated_document_count(self):
        return 7

    def list_indexes(self):
        return [{"name": "_id_"}, {"name": "sample_id_1"}]


class FakeMongoDatabase:
    def __init__(self, name: str) -> None:
        self.name = name

    def __getitem__(self, collection_name: str):
        if collection_name == "variants":
            return FakeCollection()
        return type(
            "Collection",
            (),
            {
                "name": collection_name,
                "database": FakeDatabase(),
                "estimated_document_count": lambda self: 1,
                "list_indexes": lambda self: [{"name": "_id_"}],
            },
        )()


def fake_adapter(*, repositories: list[tuple[str, object]]) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            config={
                "COYOTE3_DB": "coyote3_test",
                "IDENTITY_DB": "identity_test",
                "KNOWLEDGEBASE_DB": "knowledgebase_test",
                "BAM_DB": "bam_test",
                "DB_COLLECTIONS_CONFIG": {
                    "coyote3_test": {
                        "variants_collection": "variants",
                        "samples_collection": "samples",
                    },
                    "identity_test": {"users_collection": "users"},
                    "knowledgebase_test": {},
                    "bam_test": {},
                },
            }
        ),
        coyote_db=FakeMongoDatabase("coyote3_test"),
        identity_db=FakeMongoDatabase("identity_test"),
        knowledgebase_db=FakeMongoDatabase("knowledgebase_test"),
        bam_db=FakeMongoDatabase("bam_test"),
        iter_repositories=lambda: iter(repositories),
    )


def test_collection_snapshot_uses_metadata_only() -> None:
    result = collection_snapshot(FakeCollection())

    assert result["collection"] == "variants"
    assert result["estimated_document_count"] == 7
    assert result["storage_bytes"] == 20
    assert result["data_bytes"] == 12
    assert result["index_bytes"] == 8
    assert result["indexes"] == ["_id_", "sample_id_1"]


def test_snapshot_filters_and_sorts_managed_collections() -> None:
    variants = FakeCollection()
    adapter = fake_adapter(
        repositories=[("variants", SimpleNamespace(get_collection=lambda: variants))]
    )

    assert [item["collection"] for item in snapshot(adapter, set())] == [
        "samples",
        "variants",
        "users",
    ]
    assert [item["collection"] for item in snapshot(adapter, {"variants"})] == ["variants"]


def test_snapshot_rejects_unknown_collection() -> None:
    variants = FakeCollection()
    adapter = fake_adapter(
        repositories=[("variants", SimpleNamespace(get_collection=lambda: variants))]
    )

    try:
        snapshot(adapter, {"not_a_managed_collection"})
    except ValueError as error:
        assert str(error) == "Unknown configured collection(s): not_a_managed_collection"
    else:  # pragma: no cover - explicit assertion makes the command contract clear
        raise AssertionError("Expected unknown collections to be rejected")
