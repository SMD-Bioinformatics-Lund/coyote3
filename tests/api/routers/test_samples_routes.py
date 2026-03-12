"""Behavior tests for sample/coverage mutation API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from api.routers import samples
from tests.fixtures.api import mock_collections as fx


def test_update_sample_filters_rejects_invalid_filters_payload(monkeypatch):
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())

    with pytest.raises(HTTPException) as exc:
        samples.update_sample_filters_mutation("S1", payload={"filters": "bad"}, user=fx.api_user())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid filters payload"


def test_reset_sample_filters_requires_assay_config(monkeypatch):
    sample = fx.sample_doc()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(samples, "get_formatted_assay_config", lambda _sample: None)

    with pytest.raises(HTTPException) as exc:
        samples.reset_sample_filters_mutation("S1", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Assay config not found for sample"


def test_update_coverage_blacklist_gene_returns_status_message(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        samples,
        "_samples_repo",
        lambda: SimpleNamespace(
            blacklist_gene=lambda gene, smp_grp: calls.setdefault("gene", (gene, smp_grp))
        ),
    )
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.update_coverage_blacklist_mutation(
        payload={"gene": "TP53", "status": "blacklisted", "smp_grp": "dna", "region": "gene"},
        user=fx.api_user(),
    )

    assert calls["gene"] == ("TP53", "dna")
    assert payload["status"] == "ok"
    assert "TP53" in payload["message"]
