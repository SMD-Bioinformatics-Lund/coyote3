"""Tests for hash-first variant identity lookups in variants handler."""

from __future__ import annotations

from api.infra.db.variants import VariantsHandler


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, _n):
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self):
        self.query = None
        self.projection = None

    def find(self, query, projection=None):
        self.query = query
        self.projection = projection
        return _FakeCursor([])


class _FakeAdapter:
    def __init__(self):
        self.variants_collection = _FakeCollection()


def test_get_variants_by_identity_uses_hash_and_simple_id() -> None:
    handler = VariantsHandler(_FakeAdapter())
    handler.get_variants_by_identity(simple_id="17_7579472_C_T", sample_id="s1")

    assert handler.get_collection().query == {
        "simple_id_hash": "862b46287a08e369aa99f8f3777f44b9",
        "simple_id": "17_7579472_C_T",
        "SAMPLE_ID": "s1",
    }


def test_get_variants_by_gene_plus_variant_list_hashes_simple_id_filters() -> None:
    handler = VariantsHandler(_FakeAdapter())
    handler.get_variants_by_gene_plus_variant_list(
        gene="TP53",
        variant_list=["17_7579472_C_T", "p.R175H"],
    )
    query = handler.get_collection().query
    assert query["genes"] == "TP53"
    assert {"HGVSp": {"$in": ["17_7579472_C_T", "p.R175H"]}} in query["$or"]
    assert {"HGVSc": {"$in": ["17_7579472_C_T", "p.R175H"]}} in query["$or"]
    assert {
        "simple_id_hash": "862b46287a08e369aa99f8f3777f44b9",
        "simple_id": "17_7579472_C_T",
    } in query["$or"]
    assert {"simple_id": {"$in": ["17_7579472_C_T", "p.R175H"]}} not in query["$or"]
