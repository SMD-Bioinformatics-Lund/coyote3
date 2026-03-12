"""Behavior tests for sample list and sample workflow API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import samples
from api.services import sample_catalog_service as sample_catalog_service_module
from api.services.sample_catalog_service import SampleCatalogService
from tests.fixtures.api import mock_collections as fx


def test_home_samples_read_returns_live_and_done(monkeypatch):
    """Handle test home samples read returns live and done.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = SampleCatalogService()

    def _get_samples(**kwargs):
        """Handle  get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        if kwargs.get("report"):
            return [{"_id": "d1", "reports": [{"time_created": 123}]}, {"_id": "d2"}]
        return [{"_id": "l1"}, {"_id": "l2"}]

    monkeypatch.setattr(sample_catalog_service_module, "runtime_app", type("_App", (), {"config": {"REPORTED_SAMPLES_SEARCH_LIMIT": 50}})())
    monkeypatch.setattr(service.repository, "get_samples", _get_samples)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.list_samples_read(
        status="live",
        search_mode="both",
        sample_view=None,
        page=2,
        per_page=1,
        live_page=2,
        done_page=2,
        live_per_page=1,
        done_per_page=1,
        profile_scope="production",
        user=user,
        service=service,
    )
    assert len(payload["live_samples"]) == 1
    assert len(payload["done_samples"]) == 1
    assert payload["sample_view"] == "all"
    assert payload["live_page"] == 2
    assert payload["done_page"] == 2
    assert payload["live_per_page"] == 1
    assert payload["done_per_page"] == 1
    assert payload["profile_scope"] == "production"
    assert payload["has_next_live"] is True
    assert payload["has_next_done"] is True
    assert all(call["offset"] == 1 for call in calls)


def test_home_samples_read_always_fetches_both_tables(monkeypatch):
    """Handle test home samples read always fetches both tables.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = SampleCatalogService()

    def _get_samples(**kwargs):
        """Handle  get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        return [{"_id": "d1", "reports": [{"time_created": 123}]}]

    monkeypatch.setattr(sample_catalog_service_module, "runtime_app", type("_App", (), {"config": {"REPORTED_SAMPLES_SEARCH_LIMIT": 50}})())
    monkeypatch.setattr(service.repository, "get_samples", _get_samples)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.list_samples_read(
        status="live",
        search_mode="live",
        sample_view="reported",
        page=1,
        per_page=30,
        live_page=1,
        done_page=1,
        live_per_page=30,
        done_per_page=30,
        profile_scope="all",
        user=user,
        service=service,
    )

    assert payload["sample_view"] == "all"
    assert payload["profile_scope"] == "all"
    assert len(payload["live_samples"]) == 1
    assert len(payload["done_samples"]) == 1
    assert len(calls) == 2
    assert any(call["report"] is True and call["status"] == "done" for call in calls)
    assert any(call["report"] is False and call["status"] == "live" for call in calls)


def test_home_apply_isgl_invalid_payload_raises_400(monkeypatch):
    """Handle test home apply isgl invalid payload raises 400.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())

    with pytest.raises(HTTPException) as exc:
        samples.sample_apply_genelists_mutation("S1", payload={"isgl_ids": "bad"}, user=fx.api_user(), service=SampleCatalogService())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid isgl_ids payload"


def test_home_save_adhoc_genes_mutation_parses_and_sorts(monkeypatch):
    """Handle test home save adhoc genes mutation parses and sorts.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    calls = {}
    service = SampleCatalogService()

    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)

    def _update_sample_filters(sample_id, filters):
        """Handle  update sample filters.

        Args:
                sample_id: Sample id.
                filters: Filters.

        Returns:
                The  update sample filters result.
        """
        calls["filters"] = filters

    monkeypatch.setattr(service.repository, "update_sample_filters", _update_sample_filters)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.sample_save_adhoc_genes_mutation(
        "S1",
        payload={"genes": "NPM1 TP53\nIDH1", "label": "focus"},
        user=fx.api_user(),
        service=service,
    )

    assert payload["action"] == "save_adhoc_genes"
    assert payload["gene_count"] == 3
    assert calls["filters"]["adhoc_genes"]["genes"] == ["IDH1", "NPM1", "TP53"]
