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

    def find(self, query, projection=None):
        self.query = query
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
