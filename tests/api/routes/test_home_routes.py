"""Behavior tests for Home API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes import home
from tests.api.fixtures import mock_collections as fx


def test_home_samples_read_returns_live_and_done(monkeypatch):
    user = fx.api_user()

    def _get_samples(**kwargs):
        if kwargs.get("report"):
            return [{"_id": "d1", "reports": [{"time_created": 123}]}]
        return [{"_id": "l1"}]

    monkeypatch.setattr(home.runtime_app, "config", {"REPORTED_SAMPLES_SEARCH_LIMIT": 50})
    monkeypatch.setattr(home.store.sample_handler, "get_samples", _get_samples)
    monkeypatch.setattr(home.util.common, "get_date_days_ago", lambda days: "DATE")
    monkeypatch.setattr(home.util.common, "convert_to_serializable", lambda payload: payload)

    payload = home.home_samples_read(status="live", search_mode="both", user=user)
    assert len(payload["live_samples"]) == 1
    assert len(payload["done_samples"]) == 1


def test_home_apply_isgl_invalid_payload_raises_400(monkeypatch):
    monkeypatch.setattr(home, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())

    with pytest.raises(HTTPException) as exc:
        home.home_apply_isgl_mutation("S1", payload={"isgl_ids": "bad"}, user=fx.api_user())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid isgl_ids payload"


def test_home_save_adhoc_genes_mutation_parses_and_sorts(monkeypatch):
    sample = fx.sample_doc()
    calls = {}

    monkeypatch.setattr(home, "_get_sample_for_api", lambda sample_id, user: sample)

    def _update_sample_filters(sample_id, filters):
        calls["filters"] = filters

    monkeypatch.setattr(home.store.sample_handler, "update_sample_filters", _update_sample_filters)
    monkeypatch.setattr(home.util.common, "convert_to_serializable", lambda payload: payload)

    payload = home.home_save_adhoc_genes_mutation(
        "S1",
        payload={"genes": "NPM1 TP53\nIDH1", "label": "focus"},
        user=fx.api_user(),
    )

    assert payload["action"] == "save_adhoc_genes"
    assert payload["gene_count"] == 3
    assert calls["filters"]["adhoc_genes"]["genes"] == ["IDH1", "NPM1", "TP53"]
