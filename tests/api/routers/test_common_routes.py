"""Behavior tests for Common API routes using collection-shaped fixtures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.app.deps.services import get_common_query_service
from api.infra.mongo.selection import compile_selection
from api.interfaces.http.v1.knowledgebase import common
from coyote3.application.common.query_service import CommonQueryService
from coyote3.application.operations import knowledgebase as sdk_knowledgebase
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


def _knowledgebase_service() -> CommonQueryService:
    """Build a common service with external knowledgebase fakes."""
    return CommonQueryService(
        hgnc_repository=SimpleNamespace(
            get_metadata_by_symbol_or_alias=lambda symbol: {
                "hgnc_symbol": symbol,
                "hgnc_id": "HGNC:1",
            },
            get_metadata_by_hgnc_id=lambda hgnc_id: {
                "hgnc_symbol": "TP53",
                "hgnc_id": hgnc_id,
            },
        ),
        oncokb_repository=SimpleNamespace(
            get_oncokb_gene=lambda gene: {"name": gene},
            get_oncokb_action_gene=lambda gene: {"Hugo Symbol": gene, "Level": "1"},
            get_oncokb_anno=lambda variant, hgvsp: {
                "Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"]
            },
            get_oncokb_action=lambda variant, hgvsp: [
                {"Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"], "Alteration": hgvsp[0]}
            ],
        ),
        variant_repository=SimpleNamespace(get_variant=lambda variant_id: None),
        reported_variant_repository=SimpleNamespace(list_reported_variants=lambda query: []),
        assay_panel_repository=SimpleNamespace(get_all_asp_groups=lambda: []),
        annotation_repository=SimpleNamespace(),
        sample_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(get_isgl_by_ids=lambda ids: {}),
        oncokb_public_cache_repository=SimpleNamespace(
            get_gene_record=lambda gene: {"gene": gene, "public_api": True}
        ),
        clinpgx_public_repository=SimpleNamespace(
            get_gene_record=lambda gene: {"symbol": gene, "pharmgkb_accession_id": "PA1"}
        ),
        civic_repository=SimpleNamespace(
            get_civic_gene_info=lambda gene: {"name": gene},
            get_civic_data=lambda variant, desc: [
                {"gene": variant["INFO"]["selected_CSQ"]["SYMBOL"]}
            ],
        ),
        brca_repository=SimpleNamespace(get_brca_data=lambda variant, assay: {"source": "brca"}),
        iarc_tp53_repository=SimpleNamespace(find_iarc_tp53=lambda variant: {"source": "iarc"}),
    )


def test_common_gene_info_read_by_symbol(monkeypatch):
    service = get_common_query_service()
    monkeypatch.setattr(
        service.hgnc_repository,
        "get_metadata_by_symbol_or_alias",
        lambda symbol: {"symbol": symbol},
    )
    monkeypatch.setattr(service.oncokb_repository, "get_oncokb_gene", lambda symbol: {})
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.common_gene_info_read,
        "TP53",
        service=sdk_fixtures.public_gene_operations(service),
    )
    assert payload["gene"]["symbol"] == "TP53"


def test_common_gene_cohort_read_applies_user_scope(monkeypatch):
    captured = {}
    service = SimpleNamespace(
        gene_cohort_payload=lambda **kwargs: (
            captured.update(kwargs)
            or {
                "query": {},
                "gene": None,
                "summary": {},
                "denominator": {},
                "tier_counts": {},
                "assays": [],
                "sex_distribution": [],
                "recurrent_findings": [],
                "samples": [],
                "truncated": False,
            }
        )
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)
    user = fx.api_user()
    user.roles = ["user"]
    user.role = "user"
    user.asp_ids = ["demo-solid_gmsv3"]
    user.envs = ["production"]
    sdk_fixtures.invoke_route(
        common.common_gene_cohort_read,
        "TP53",
        user=user,
        service=sdk_fixtures.authorized_operations(sdk_knowledgebase.Knowledgebase, service, user),
    )
    assert captured == {
        "gene_id": "TP53",
        "visible_asp_ids": ["demo-solid_gmsv3"],
        "visible_environments": ["production"],
        "include_history": False,
    }


def test_common_gene_cohort_read_can_include_report_history(monkeypatch):
    captured = {}
    service = SimpleNamespace(
        gene_cohort_payload=lambda **kwargs: (
            captured.update(kwargs)
            or {
                "query": {},
                "gene": None,
                "summary": {},
                "denominator": {},
                "tier_counts": {},
                "assays": [],
                "sex_distribution": [],
                "recurrent_findings": [],
                "samples": [],
                "truncated": False,
            }
        )
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    sdk_fixtures.invoke_route(
        common.common_gene_cohort_read,
        "TP53",
        include_history=True,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert captured["include_history"] is True


def test_knowledgebase_statistics_read_returns_aggregate_sources(monkeypatch):
    service = SimpleNamespace(
        knowledgebase_statistics=lambda: {
            "sources": [
                {
                    "key": "oncokb",
                    "name": "OncoKB",
                    "available": True,
                    "total": 42,
                    "unit": "genes",
                    "distribution": [],
                    "metrics": [],
                }
            ]
        }
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.knowledgebase_statistics_read,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert payload["sources"][0]["total"] == 42


def test_knowledgebase_gene_read_returns_external_sources(monkeypatch):
    """Aggregated gene knowledgebase endpoint should expose configured source blocks."""
    service = _knowledgebase_service()
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.knowledgebase_gene_read,
        "TP53",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert payload["query"]["resolved_symbol"] == "TP53"
    assert payload["sources"]["oncokb_public"]["gene"] == "TP53"
    assert payload["sources"]["clinpgx_public"]["pharmgkb_accession_id"] == "PA1"
    assert "oncokb_public" in payload["available_sources"]


def test_cancer_gene_census_summary_read_returns_repository_aggregate(monkeypatch):
    service = SimpleNamespace(
        cancer_gene_census_summary=lambda: {
            "available": True,
            "total_genes": 1,
            "tiers": [{"name": "Tier 1", "value": 1}],
        }
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.cancer_gene_census_summary_read,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert payload["available"] is True
    assert payload["total_genes"] == 1


def test_knowledgebase_variant_evidence_read_returns_variant_sources(monkeypatch):
    """Variant evidence endpoint should query local coordinate and HGVS knowledgebases."""
    service = _knowledgebase_service()
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.knowledgebase_variant_evidence_read,
        chrom="17",
        pos=76736896,
        ref="T",
        alt="C",
        gene="SRSF2",
        hgvsp="p.Met89Val",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert payload["query"]["gene"] == "SRSF2"
    assert payload["sources"]["civic_variants"][0]["gene"] == "SRSF2"
    assert payload["sources"]["oncokb_actionable_local"][0]["Alteration"] == "p.Met89Val"


def test_source_specific_knowledgebase_routes_filter_sources(monkeypatch):
    """Dedicated knowledgebase routes should expose only their source family."""
    service = _knowledgebase_service()
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    civic_gene = sdk_fixtures.invoke_route(
        common.knowledgebase_civic_gene_read,
        "TP53",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    brca_gene = sdk_fixtures.invoke_route(
        common.knowledgebase_brca_exchange_gene_read,
        "BRCA1",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    iarc_gene = sdk_fixtures.invoke_route(
        common.knowledgebase_iarc_tp53_gene_read,
        "TP53",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    civic_variant = sdk_fixtures.invoke_route(
        common.knowledgebase_civic_variant_evidence_read,
        chrom="17",
        pos=76736896,
        ref="T",
        alt="C",
        gene="SRSF2",
        hgvsp="p.Met89Val",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    brca_variant = sdk_fixtures.invoke_route(
        common.knowledgebase_brca_exchange_variant_evidence_read,
        chrom="17",
        pos=76736896,
        ref="T",
        alt="C",
        gene="BRCA1",
        hgvsp="p.Met89Val",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    iarc_variant = sdk_fixtures.invoke_route(
        common.knowledgebase_iarc_tp53_variant_evidence_read,
        chrom="17",
        pos=76736896,
        ref="T",
        alt="C",
        gene="TP53",
        hgvsp="p.Met89Val",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert set(civic_gene["sources"]) == {"civic_gene"}
    assert set(brca_gene["sources"]) == {"brca_exchange"}
    assert set(iarc_gene["sources"]) == {"iarc_tp53"}
    assert set(civic_variant["sources"]) == {"civic_variants"}
    assert set(brca_variant["sources"]) == {"brca_exchange"}
    assert set(iarc_variant["sources"]) == {"iarc_tp53"}


def test_common_tiered_variant_context_not_found_raises_404(monkeypatch):
    service = get_common_query_service()
    monkeypatch.setattr(service.variant_repository, "get_variant", lambda variant_id: None)

    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            common.common_tiered_variant_context_read,
            "missing",
            2,
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_knowledgebase.Knowledgebase, service, fx.api_user()
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_common_tiered_variant_context_insufficient_identity_returns_error_payload(monkeypatch):
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *_: fx.sample_doc())
    variant = {
        "_id": "v1",
        "SAMPLE_ID": "s1",
        "INFO": {"selected_CSQ": {}},
        "simple_id": None,
        "simple_id_hash": None,
    }
    service = get_common_query_service()
    monkeypatch.setattr(service.variant_repository, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.common_tiered_variant_context_read,
        "v1",
        3,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )
    assert payload["docs"] == []
    assert payload["tier"] == 3
    assert payload["error"] == "Variant has insufficient identity fields"


def test_common_tiered_variant_context_uses_master_style_identity_lookup(monkeypatch):
    """Exact identity lookup should match historical reported-variant behavior."""
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *_: fx.sample_doc())
    variant = {
        "_id": "v1",
        "SAMPLE_ID": "s1",
        "simple_id": " chr17_7579472_c_t ",
        "simple_id_hash": None,
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53"}},
    }
    captured: dict = {}

    def _list_reported_variants(query):
        captured["query"] = query
        return []

    service = get_common_query_service()
    monkeypatch.setattr(service.variant_repository, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(
        service.reported_variant_repository,
        "list_reported_variants",
        _list_reported_variants,
    )
    monkeypatch.setattr(
        "coyote3.application.common.query_service.enrich_reported_variant_docs",
        lambda docs, **_: docs,
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        common.common_tiered_variant_context_read,
        "v1",
        2,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_knowledgebase.Knowledgebase, service, fx.api_user()
        ),
    )

    assert payload["error"] is None
    assert compile_selection(captured["query"]) == {
        "gene": "TP53",
        "$or": [{"simple_id_hash": "862b46287a08e369aa99f8f3777f44b9"}],
    }
