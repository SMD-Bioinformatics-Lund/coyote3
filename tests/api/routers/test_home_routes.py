"""Behavior tests for sample list and sample workflow API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api.app.container import store
from api.application.sample import catalog as sample_catalog_service_module
from api.application.sample.catalog import SampleCatalogService
from api.domain.core.exceptions import AppError
from api.interfaces.http.clinical import samples
from tests.fixtures.api import mock_collections as fx


def _sample_catalog_service() -> SampleCatalogService:
    return SampleCatalogService(
        sample_repository=store.sample_repository,
        gene_list_repository=store.gene_list_repository,
        assay_panel_repository=store.assay_panel_repository,
        variant_repository=store.variant_repository,
        copy_number_variant_repository=store.copy_number_variant_repository,
        fusion_repository=store.fusion_repository,
        translocation_repository=store.translocation_repository,
        biomarker_repository=SimpleNamespace(
            get_sample_biomarkers=lambda sample_id: [],
            get_samples_biomarkers=lambda sample_ids: {
                str(sample_id): [] for sample_id in sample_ids
            },
        ),
        grouped_coverage_repository=store.grouped_coverage_repository,
        sample_comment_repository=SimpleNamespace(
            list_sample_comments=lambda sample_id: [],
        ),
    )


def test_home_samples_read_returns_live_and_done(monkeypatch):
    """Test home samples read returns live and done.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = _sample_catalog_service()

    def _get_samples_page(**kwargs):
        """Get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        if kwargs.get("report"):
            return {
                "items": [{"_id": "d1", "reports": [{"time_created": 123}]}],
                "total": 3,
            }
        return {"items": [{"_id": "l1"}], "total": 3}

    monkeypatch.setattr(service.sample_repository, "get_samples_page", _get_samples_page)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    added_from = datetime(2026, 8, 1, tzinfo=timezone.utc)
    added_until = datetime(2026, 8, 4, tzinfo=timezone.utc)
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
        added_from=added_from,
        added_until=added_until,
        live_sort="",
        reported_sort="latest_reported:desc",
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
    assert payload["live_total"] == 3
    assert payload["done_total"] == 3
    assert payload["profile_scope"] == "production"
    assert payload["has_next_live"] is True
    assert payload["has_next_done"] is True
    assert all(call["offset"] == 1 for call in calls)
    assert all(call["added_from"] == added_from for call in calls)
    assert all(call["added_until"] == added_until for call in calls)
    assert next(call for call in calls if call["report"] is False)["sort"] == ""
    assert next(call for call in calls if call["report"] is True)["sort"] == "latest_reported:desc"


def test_home_samples_read_always_fetches_both_tables(monkeypatch):
    """Test home samples read always fetches both tables.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = _sample_catalog_service()

    def _get_samples_page(**kwargs):
        """Get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        return {"items": [{"_id": "d1", "reports": [{"time_created": 123}]}], "total": 1}

    monkeypatch.setattr(service.sample_repository, "get_samples_page", _get_samples_page)
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
        live_sort="",
        reported_sort="",
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


def test_home_samples_read_superuser_is_unscoped(monkeypatch):
    """Superusers should fetch all samples without assay or environment restrictions."""
    user = fx.api_user()
    user.roles = ["superuser"]
    user.asp_ids = ["WGS"]
    user.envs = ["production"]
    calls = []
    service = _sample_catalog_service()

    def _get_samples_page(**kwargs):
        calls.append(kwargs)
        return {"items": [], "total": 0}

    monkeypatch.setattr(service.sample_repository, "get_samples_page", _get_samples_page)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.list_samples_read(
        status="live",
        search_mode="both",
        sample_view=None,
        page=1,
        per_page=30,
        live_page=1,
        done_page=1,
        live_per_page=30,
        done_per_page=30,
        profile_scope="all",
        live_sort="",
        reported_sort="",
        user=user,
        service=service,
    )

    assert payload["profile_scope"] == "all"
    assert len(calls) == 2
    assert all(call["user_assays"] is None for call in calls)
    assert all(call["user_envs"] is None for call in calls)


def test_home_apply_isgl_invalid_payload_raises_400(monkeypatch):
    """Test home apply isgl invalid payload raises 400.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())

    with pytest.raises(AppError) as exc:
        samples.sample_apply_genelists_change(
            "S1", payload={"isgl_ids": "bad"}, user=fx.api_user(), service=_sample_catalog_service()
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid isgl_ids payload"


def test_home_apply_isgl_rejects_list_for_different_analysis_type(monkeypatch):
    """The API must reject an SNV-only list submitted to the CNV filter section."""
    sample = fx.sample_doc()
    service = _sample_catalog_service()
    monkeypatch.setattr(
        service.gene_list_repository,
        "get_isgl_by_ids",
        lambda ids: {"SNV_ONLY": {"list_type": ["snv"], "genes": ["TP53"]}},
    )

    with pytest.raises(AppError) as exc:
        service.apply_genelists(
            sample=sample,
            payload={"isgl_ids": ["SNV_ONLY"]},
            sample_id="S1",
            target="cnv",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == ("Gene list(s) do not support CNV analysis: SNV_ONLY")


def test_replace_sample_filters_rejects_snv_list_in_cnv_section(monkeypatch):
    """Full filter updates must enforce the same analysis-specific ISGL boundary."""
    sample = fx.sample_doc()
    service = _sample_catalog_service()
    submitted = {
        "somatic": {
            "snv": {"snvlists": []},
            "cnv": {"cnvlists": ["SNV_ONLY"]},
        }
    }
    monkeypatch.setattr(
        service,
        "_get_formatted_assay_config",
        lambda sample_doc: {"filters": submitted},
    )
    monkeypatch.setattr(
        service.gene_list_repository,
        "get_isgl_by_ids",
        lambda ids: {"SNV_ONLY": {"list_type": ["snv"], "genes": ["TP53"]}} if ids else {},
    )
    monkeypatch.setattr(
        service.sample_repository,
        "update_sample_filters",
        lambda sample_id, filters: pytest.fail("invalid filters must not be persisted"),
    )

    with pytest.raises(AppError) as exc:
        service.replace_sample_filters(sample=sample, filters=submitted)

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == ("Gene list(s) do not support CNV analysis: SNV_ONLY")


def test_home_save_adhoc_genes_mutation_parses_and_sorts(monkeypatch):
    """Test home save adhoc genes mutation parses and sorts.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    calls = {}
    service = _sample_catalog_service()

    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)

    def _update_sample_filters(sample_id, filters):
        """Update sample filters.

        Args:
                sample_id: Sample id.
                filters: Filters.

        Returns:
                The  update sample filters result.
        """
        calls["filters"] = filters

    monkeypatch.setattr(service.sample_repository, "update_sample_filters", _update_sample_filters)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.sample_save_adhoc_genes_change(
        "S1",
        payload={"genes": "NPM1 TP53\nIDH1", "label": "focus", "list_type": "cnv"},
        user=fx.api_user(),
        service=service,
    )

    assert payload["action"] == "save_adhoc_genes"
    assert payload["gene_count"] == 3
    assert payload["list_type"] == "cnv"
    assert calls["filters"]["somatic"]["cnv"]["adhoc_genes"]["genes"] == [
        "IDH1",
        "NPM1",
        "TP53",
    ]
    assert calls["filters"]["somatic"]["cnv"]["adhoc_genes"]["label"] == "focus"


def test_edit_context_payload_includes_analysis_counts(monkeypatch):
    """Edit context should expose raw and gene-filtered counts for other analysis types too."""
    sample = fx.sample_doc()
    sample["_id"] = "s1"
    sample["omics_layer"] = "dna"
    sample["filters"]["somatic"]["snv"]["snvlists"] = ["gl1"]
    sample["filters"]["somatic"]["cnv"]["cnvlists"] = ["gl1"]
    sample["filters"]["somatic"]["snv"]["adhoc_genes"] = {}
    service = _sample_catalog_service()

    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        lambda assay: {"asp_group": "dna", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        sample_catalog_service_module,
        "get_formatted_assay_config",
        lambda sample_doc, **_kwargs: {"filters": dict(sample_doc.get("filters") or {})},
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp_genes",
        lambda assay: (["TP53", "NPM1"], []),
    )
    monkeypatch.setattr(
        service.gene_list_repository,
        "get_isgl_by_ids",
        lambda ids: {
            "gl1": {
                "genes": ["TP53"],
                "list_type": ["snv", "cnv"],
                "is_active": True,
            }
        },
    )
    monkeypatch.setattr(service.gene_list_repository, "get_isgl_for_scope", lambda **kwargs: [])
    monkeypatch.setattr(
        service.variant_repository,
        "get_variant_stats",
        lambda sample_id, genes=None: {
            "variants": 10 if genes is None else 4,
            "interesting": 2 if genes is None else 1,
            "irrelevant": 1,
            "false_positives": 0,
        },
    )
    monkeypatch.setattr(
        service.copy_number_variant_repository,
        "get_sample_cnvs",
        lambda query: [
            {"genes": [{"gene": "TP53"}]},
            {"genes": [{"gene": "RUNX1"}]},
        ],
    )
    monkeypatch.setattr(
        service.translocation_repository,
        "get_sample_translocations",
        lambda sample_id: [
            {"INFO": [{"ANN": [{"Gene_Name": "TP53&ABL1"}]}]},
            {"INFO": [{"ANN": [{"Gene_Name": "RUNX1&ETV6"}]}]},
        ],
    )
    monkeypatch.setattr(
        service.fusion_repository,
        "get_sample_fusions",
        lambda query: [],
    )
    monkeypatch.setattr(
        service.biomarker_repository,
        "get_sample_biomarkers",
        lambda sample_id: [{"name": "TMB"}],
    )

    payload = service.edit_context_payload(sample=sample)

    assert payload["analysis_counts_raw"] == {
        "snv": 10,
        "cnv": 2,
        "transloc": 2,
        "fusion": 0,
        "biomarker": 1,
    }
    assert payload["analysis_counts_filtered"] == {
        "snv": 4,
        "cnv": 1,
        "transloc": 1,
        "fusion": 0,
        "biomarker": 1,
    }


def test_edit_context_payload_uses_assay_merged_filters_for_counts(monkeypatch):
    """Edit-context counts should seed from ASPC only when the sample has no filters doc."""
    sample = fx.sample_doc()
    sample["_id"] = "s1"
    sample["omics_layer"] = "dna"
    sample["filters"] = None
    service = _sample_catalog_service()

    monkeypatch.setattr(
        sample_catalog_service_module,
        "get_formatted_assay_config",
        lambda sample_doc, **_kwargs: {"filters": {"somatic": {"snv": {"snvlists": ["gl1"]}}}},
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp",
        lambda assay: {"asp_group": "dna", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        service.assay_panel_repository,
        "get_asp_genes",
        lambda assay: (["TP53", "NPM1"], []),
    )
    monkeypatch.setattr(
        service.gene_list_repository,
        "get_isgl_by_ids",
        lambda ids: {
            "gl1": {
                "genes": ["TP53"],
                "list_type": ["snv"],
                "is_active": True,
            }
        },
    )
    monkeypatch.setattr(service.gene_list_repository, "get_isgl_for_scope", lambda **kwargs: [])
    service.sample_repository = SimpleNamespace(
        reset_sample_settings=lambda sample_id, filters, **_kwargs: None,
        get_sample=lambda sample_id: {
            **sample,
            "_id": sample_id,
            "filters": {"somatic": {"snv": {"snvlists": ["gl1"]}}},
        },
    )
    monkeypatch.setattr(
        service.variant_repository,
        "get_variant_stats",
        lambda sample_id, genes=None: {
            "variants": 6 if genes is None else 2,
            "interesting": 1,
            "irrelevant": 0,
            "false_positives": 0,
        },
    )
    monkeypatch.setattr(service.copy_number_variant_repository, "get_sample_cnvs", lambda query: [])
    monkeypatch.setattr(
        service.translocation_repository, "get_sample_translocations", lambda sample_id: []
    )
    monkeypatch.setattr(service.fusion_repository, "get_sample_fusions", lambda query: [])
    monkeypatch.setattr(service.biomarker_repository, "get_sample_biomarkers", lambda sample_id: [])

    payload = service.edit_context_payload(sample=sample)

    assert payload["sample"]["filters"]["somatic"]["snv"]["snvlists"] == ["gl1"]
    assert payload["analysis_counts_filtered"]["snv"] == 2
