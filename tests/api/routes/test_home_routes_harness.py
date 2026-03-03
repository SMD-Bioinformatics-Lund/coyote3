"""Integration-style home route tests using shared fake-store harness."""

from __future__ import annotations

from api.routes import home
from tests.api.fixtures import mock_collections as fx
from tests.api.fixtures.fake_store import build_fake_store


def test_home_isgls_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(home, "store", fake_store)
    monkeypatch.setattr(home, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(home.util.common, "convert_to_serializable", lambda payload: payload)

    payload = home.home_isgls_read("S1", user=fx.api_user())

    assert payload["items"][0]["_id"] == str(fx.isgl_doc()["_id"])
    assert payload["items"][0]["gene_count"] == int(fx.isgl_doc().get("gene_count") or 0)


def test_home_effective_genes_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(home, "store", fake_store)
    monkeypatch.setattr(home, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(home.util.common, "convert_to_serializable", lambda payload: payload)

    payload = home.home_effective_genes_read("S1", user=fx.api_user())

    assert "items" in payload
    assert payload["asp_covered_genes_count"] >= 1
