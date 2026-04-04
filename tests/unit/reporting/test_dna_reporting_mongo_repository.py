"""Unit tests for Mongo DNA reporting repository adapter."""

from __future__ import annotations

from types import SimpleNamespace

from api.infra.repositories import dna_reporting_mongo


def test_get_isgl_by_ids_returns_dict_shape(monkeypatch):
    """Ensure ISGL lookup preserves dict shape for downstream gene filtering."""
    fake_isgl = {"gms-hem": {"is_active": True, "genes": ["TP53"]}}
    monkeypatch.setattr(
        dna_reporting_mongo,
        "store",
        SimpleNamespace(isgl_handler=SimpleNamespace(get_isgl_by_ids=lambda _ids: fake_isgl)),
    )

    repo = dna_reporting_mongo.ReportRepository()
    payload = repo.get_isgl_by_ids(["gms-hem"])

    assert payload == fake_isgl
    assert isinstance(payload, dict)
