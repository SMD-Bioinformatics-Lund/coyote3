"""Behavioral tests for immutable versioned VEP annotation evidence."""

from __future__ import annotations

from types import SimpleNamespace

import mongomock

from api.infra.mongo.repositories.anno_vep import AnnoVepRepository


def _repository() -> AnnoVepRepository:
    database = mongomock.MongoClient()["coyote3_test"]
    return AnnoVepRepository(SimpleNamespace(anno_vep_collection=database.anno_vep))


def test_vep_evidence_is_immutable_per_variant_and_release(
    monkeypatch,
) -> None:
    """A duplicate release is represented by a set-on-insert-only operation."""
    repository = _repository()
    operations = []

    def capture_bulk_write(values, **_kwargs):
        operations.extend(values)
        return SimpleNamespace(upserted_count=2)

    monkeypatch.setattr(repository.get_collection(), "bulk_write", capture_bulk_write)

    initial = {
        "simple_id_hash": "variant-one",
        "vep_version": "103",
        "CSQ": [{"Feature": "NM_000546.6", "SYMBOL": "TP53"}],
    }
    assert repository.upsert_many([initial, {**initial, "vep_version": "110"}]) == 2
    assert [operation._filter for operation in operations] == [
        {"simple_id_hash": "variant-one", "vep_version": "103"},
        {"simple_id_hash": "variant-one", "vep_version": "110"},
    ]
    assert all("$setOnInsert" in operation._doc for operation in operations)
    assert all("$set" not in operation._doc for operation in operations)
