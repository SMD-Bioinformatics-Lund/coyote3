"""Behavior tests for DNA API route helpers and endpoints."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes import dna
from tests.api.fixtures import mock_collections as fx


def test_mutation_payload_shape():
    payload = dna._mutation_payload("S1", "variant", "V1", "flag")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["resource"] == "variant"
    assert payload["resource_id"] == "V1"
    assert payload["action"] == "flag"


def test_load_cnvs_for_sample_uses_collection_shaped_docs(monkeypatch):
    sample = fx.sample_doc()
    sample_filters = sample["filters"]
    cnv_rows = [fx.cnv_doc()]

    monkeypatch.setattr(dna, "build_cnv_query", lambda sample_id, filters: {"sample_id": sample_id, **filters})
    monkeypatch.setattr(dna.store.cnv_handler, "get_sample_cnvs", lambda query: cnv_rows)
    monkeypatch.setattr(dna, "create_cnveffectlist", lambda cnv_effects: [])
    monkeypatch.setattr(dna, "cnv_organizegenes", lambda cnvs: cnvs)

    rows = dna._load_cnvs_for_sample(sample, sample_filters, ["ERBB2"])
    assert rows == cnv_rows


def test_list_dna_biomarkers_success(monkeypatch):
    sample = fx.sample_doc()
    biomarkers = [{"_id": "b1", "name": "TMB", "value": "High"}]

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna.store.biomarker_handler, "get_sample_biomarkers", lambda sample_id: biomarkers)
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.list_dna_biomarkers("S1", user=fx.api_user())
    assert payload["meta"]["count"] == 1
    assert payload["biomarkers"][0]["name"] == "TMB"


def test_show_dna_variant_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna.store.variant_handler, "get_variant", lambda var_id: None)

    with pytest.raises(HTTPException) as exc:
        dna.show_dna_variant("S1", "V404", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"
