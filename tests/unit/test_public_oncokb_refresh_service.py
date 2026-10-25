"""Tests for the explicit HGNC-backed public OncoKB refresh workflow."""

from types import SimpleNamespace

import pytest

from coyote3.application.knowledgebase import oncokb_refresh


def test_disabled_refresh_does_not_read_the_external_catalogue() -> None:
    read = False

    def unexpected_read(**_kwargs):
        nonlocal read
        read = True
        raise AssertionError("disabled public lookup must not read the catalogue")

    service = oncokb_refresh.PublicOncoKbRefreshService(
        client=SimpleNamespace(cancer_gene_list=unexpected_read, all_curated_genes=unexpected_read),
        cache_repository=object(),
        hgnc_repository=object(),
        config={"ONCOKB_PUBLIC_LOOKUPS_ENABLED": False},
    )

    assert service.refresh() == {"status": "disabled"}
    assert read is False


def test_refresh_records_counts_for_a_successful_global_hgnc_refresh(monkeypatch) -> None:
    client = object()
    events: list[tuple[tuple, dict]] = []
    expected = {
        "hgnc_gene_records": 2,
        "hgnc_symbols_indexed": 4,
        "cancer_records_fetched": 3,
        "cancer_records_matched": 2,
        "cancer_genes_upserted": 2,
        "cancer_genes_removed": 1,
        "curated_records_fetched": 3,
        "curated_records_matched": 2,
        "curated_genes_upserted": 2,
        "curated_genes_removed": 1,
    }
    monkeypatch.setattr(
        oncokb_refresh,
        "refresh_public_oncokb_gene_cache",
        lambda **kwargs: expected if kwargs["client"] is client else {},
    )
    service = oncokb_refresh.PublicOncoKbRefreshService(
        client=client,
        cache_repository=object(),
        hgnc_repository=object(),
        config={
            "ONCOKB_PUBLIC_LOOKUPS_ENABLED": True,
            "ONCOKB_BASE_URL": "https://public.api.oncokb.org/api/v1",
        },
        audit_service=SimpleNamespace(record=lambda *args, **kwargs: events.append((args, kwargs))),
    )

    assert service.refresh() == {"status": "ok", **expected}
    assert events == [
        (
            (
                "knowledgebase.oncokb_public.refresh.completed",
                "Public OncoKB reference refresh completed",
            ),
            {
                "category": "operations",
                "outcome": "success",
                "resource_type": "knowledgebase",
                "resource_id": "oncokb_public",
                "tags": ["knowledgebase", "oncokb", "refresh"],
                "metadata": {
                    "hgnc_gene_records": 2,
                    "cancer_genes_upserted": 2,
                    "cancer_genes_removed": 1,
                    "curated_genes_upserted": 2,
                    "curated_genes_removed": 1,
                },
            },
        )
    ]


def test_refresh_audits_failure_without_recording_external_error_text(monkeypatch) -> None:
    events: list[tuple[tuple, dict]] = []

    def failed_refresh(**_kwargs):
        raise RuntimeError("remote endpoint diagnostic must not enter audit metadata")

    monkeypatch.setattr(oncokb_refresh, "refresh_public_oncokb_gene_cache", failed_refresh)
    service = oncokb_refresh.PublicOncoKbRefreshService(
        client=object(),
        cache_repository=object(),
        hgnc_repository=object(),
        config={"ONCOKB_BASE_URL": "https://public.api.oncokb.org/api/v1"},
        audit_service=SimpleNamespace(record=lambda *args, **kwargs: events.append((args, kwargs))),
    )

    with pytest.raises(RuntimeError, match="remote endpoint diagnostic"):
        service.refresh()

    assert events[0][0][0] == "knowledgebase.oncokb_public.refresh.failed"
    assert events[0][1]["metadata"] == {"error_type": "RuntimeError"}
