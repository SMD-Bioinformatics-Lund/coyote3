"""Extended behavior tests for shared query workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.common import query_service
from api.application.common.query_service import CommonQueryService
from api.domain.core.exceptions import AppError


class AnnotationRepository:
    """Capture search inputs while returning representative annotation records."""

    def __init__(self) -> None:
        self.stats_calls: list[dict] = []

    def find_variants_by_search_string(self, **kwargs):
        self.search = kwargs
        return [
            {"_id": "annotation-1", "gene": "TP53", "class": 2},
            {"_id": "text-1", "gene": "TP53", "class": 2, "text": "standalone"},
        ]

    def get_tier_stats_by_search(self, **kwargs):
        self.stats_calls.append(kwargs)
        return {"total": {"2": 2}, "by_assay": {"solid": {"2": 2}}}

    @staticmethod
    def get_matching_annotation_text(doc):
        return f"matched:{doc.get('_id')}"

    @staticmethod
    def get_annotation_text_by_oid(annotation_text_oid):
        return f"text:{annotation_text_oid}"

    @staticmethod
    def get_annotation_by_oid(annotation_oid):
        return {"_id": annotation_oid, "gene": "NPM1", "class": 3, "author": "reviewer"}


class ReportedRepository:
    """Return linked and direct reported variants, including one duplicate."""

    @staticmethod
    def list_reported_variants(query):
        if query.get("annotation_oid"):
            annotation_id = query["annotation_oid"]["$in"][0]
            if annotation_id == "annotation-1":
                return [
                    {
                        "_id": "reported-linked",
                        "sample_oid": "sample-1",
                        "sample_name": "stored-name",
                        "report_oid": "report-oid",
                        "report_id": "R1",
                        "report_num": 4,
                        "annotation_text_oid": "text-1",
                    }
                ]
        return []

    @staticmethod
    def find_reported_variants_by_search_string(**kwargs):
        return [
            {"_id": "reported-linked"},
            {
                "_id": "reported-direct",
                "annotation_oid": "annotation-2",
                "annotation_text_oid": "text-2",
                "sample_oid": "missing-sample",
                "sample_name": "preserved-name",
                "report_id": "R2",
                "report_num": 8,
                "tier": 3,
                "created_by": "curator",
            },
            {
                "_id": "reported-no-text",
                "sample_oid": None,
                "tier": 1,
            },
        ]


def _service(**overrides) -> CommonQueryService:
    values = {
        "hgnc_repository": SimpleNamespace(
            get_metadata_by_hgnc_id=lambda hgnc_id: {
                "hgnc_id": hgnc_id,
                "hgnc_symbol": "TP53",
            },
            get_metadata_by_symbol_or_alias=lambda symbol: {
                "hgnc_id": "HGNC:11998",
                "hgnc_symbol": "TP53" if symbol == "P53" else symbol,
            },
        ),
        "oncokb_repository": SimpleNamespace(
            get_oncokb_gene=lambda gene: {"gene": gene} if gene else None,
            get_oncokb_action_gene=lambda gene: {"gene": gene, "actionable": True},
            get_oncokb_anno=lambda variant, candidates: {"candidates": candidates},
            get_oncokb_action=lambda variant, candidates: [{"candidate": candidates[0]}],
        ),
        "variant_repository": SimpleNamespace(get_variant=lambda variant_id: None),
        "reported_variant_repository": ReportedRepository(),
        "assay_panel_repository": SimpleNamespace(
            get_all_asp_groups=lambda: ["hematology", "solid"]
        ),
        "annotation_repository": AnnotationRepository(),
        "sample_repository": SimpleNamespace(
            get_sample_by_oid=lambda oid: (
                {
                    "_id": oid,
                    "name": "database-name",
                    "asp_id": "solid_gmsv3",
                    "subpanel_id": "colon",
                    "environment": "production",
                }
                if oid == "sample-1"
                else None
            )
        ),
    }
    values.update(overrides)
    return CommonQueryService(**values)


def test_from_store_copies_required_and_optional_repositories() -> None:
    store = SimpleNamespace(
        hgnc_repository=object(),
        oncokb_repository=object(),
        variant_repository=object(),
        reported_variant_repository=object(),
        assay_panel_repository=object(),
        annotation_repository=object(),
        sample_repository=object(),
        bam_record_repository=object(),
    )
    service = CommonQueryService.from_store(store)
    assert service.hgnc_repository is store.hgnc_repository
    assert service.bam_record_repository is store.bam_record_repository
    assert service.civic_repository is None


def test_resolve_gene_uses_hgnc_alias_and_legacy_symbol_lookup() -> None:
    service = _service()
    gene, query = service._resolve_gene("HGNC:11998")
    assert gene["hgnc_symbol"] == "TP53"
    assert query["symbol_changed"] is False

    gene, query = service._resolve_gene("P53")
    assert gene["hgnc_symbol"] == "TP53"
    assert query["symbol_changed"] is True

    legacy = _service(
        hgnc_repository=SimpleNamespace(
            get_metadata_by_symbol=lambda symbol: {"symbol": symbol.upper()}
        )
    )
    assert legacy._resolve_gene("brca1")[0]["symbol"] == "BRCA1"


@pytest.mark.parametrize(
    ("value", "present"),
    [(None, False), ({}, False), ([], False), ("", True), (0, True), ("value", True)],
)
def test_source_presence_and_available_source_sorting(value, present) -> None:
    assert CommonQueryService._source_present(value) is present
    sources = {"zeta": None, "beta": {"value": 1}, "alpha": [1]}
    assert CommonQueryService._available_sources(sources) == ["alpha", "beta"]


def test_gene_and_knowledgebase_payloads_handle_configured_and_absent_plugins() -> None:
    service = _service(
        oncokb_public_cache_repository=SimpleNamespace(
            get_gene_record=lambda gene: {"public": gene}
        ),
        clinpgx_public_repository=SimpleNamespace(get_gene_record=lambda gene: {"pgx": gene}),
        civic_repository=SimpleNamespace(get_civic_gene_info=lambda gene: {"civic": gene}),
    )
    gene = service.gene_info_payload("P53")
    assert gene["knowledgebase"]["oncokb"]["gene"] == "TP53"
    assert gene["knowledgebase"]["oncokb_url"].endswith("/TP53")

    knowledgebase = service.knowledgebase_gene_payload("BRCA1")
    assert knowledgebase["sources"]["brca_exchange"]["applies_to_gene"] is True
    assert knowledgebase["sources"]["iarc_tp53"]["applies_to_gene"] is False
    assert knowledgebase["sources"]["oncokb_public"] == {"public": "BRCA1"}

    minimal = _service()
    minimal.oncokb_repository.get_oncokb_gene = lambda gene: None
    result = minimal.gene_info_payload("")
    assert result["knowledgebase"] == {"oncokb": None, "oncokb_url": None}
    assert minimal.knowledgebase_gene_payload("TP53")["sources"]["civic_gene"] is None


def test_variant_knowledgebase_payload_normalizes_identity_and_optional_sources() -> None:
    service = _service(
        civic_repository=SimpleNamespace(get_civic_data=lambda variant, desc: [desc]),
        brca_repository=SimpleNamespace(
            get_brca_data=lambda variant, group: {"group": group, "chrom": variant["CHROM"]}
        ),
        iarc_tp53_repository=SimpleNamespace(find_iarc_tp53=lambda variant: {"tp53": True}),
    )
    result = service.knowledgebase_variant_payload(
        chrom="chr17",
        pos=7579472,
        ref="C",
        alt="T",
        gene="TP53",
        hgvsc="c.215C>G",
        hgvsp="p.Pro72Arg",
        assay_group="solid",
    )
    assert result["query"]["chrom"] == "17"
    assert result["sources"]["civic_variants"] == ["p.Pro72Arg"]
    assert result["sources"]["oncokb_actionable_local"] == [{"candidate": "p.Pro72Arg"}]
    assert "iarc_tp53" in result["available_sources"]

    minimal = _service()
    no_protein = minimal.knowledgebase_variant_payload(
        chrom="1", pos=1, ref="A", alt="T", gene="GENE"
    )
    assert no_protein["sources"]["oncokb_local"] is None
    assert no_protein["sources"]["oncokb_actionable_local"] == []


def test_bam_payload_validates_input_and_handles_unconfigured_repository() -> None:
    with pytest.raises(AppError) as exc:
        _service().bam_files_payload(sample_ids=["", "  "])
    assert exc.value.status_code == 400

    assert _service().bam_files_payload(sample_ids=[" S1 "])["bam_files"] == {}
    service = _service(
        bam_record_repository=SimpleNamespace(get_bams=lambda lookup: {**lookup, "S2": "/b.bam"})
    )
    result = service.bam_files_payload(sample_ids=[" S1 ", "S2"])
    assert result["query"]["sample_ids"] == ["S1", "S2"]
    assert result["bam_files"]["S1"] == "S1"


@pytest.mark.parametrize(
    ("identity", "expected_key"),
    [
        ({"simple_id_hash": "hash"}, "simple_id_hash"),
        ({"simple_id": "1_1_A_T"}, "simple_id_hash"),
        ({"hgvsc": "c.1A>T"}, "hgvsc"),
        ({"hgvsp": "p.Lys1Asn"}, "hgvsp"),
    ],
)
def test_tiered_context_uses_supported_identity_fallbacks(
    monkeypatch, identity, expected_key
) -> None:
    csq = {"SYMBOL": "TP53"}
    if identity.get("hgvsc"):
        csq["HGVSc"] = identity["hgvsc"]
    if identity.get("hgvsp"):
        csq["HGVSp"] = identity["hgvsp"]
    variant = {"_id": "variant-1", "INFO": {"selected_CSQ": csq}, **identity}
    captured = {}

    class Reported:
        @staticmethod
        def list_reported_variants(query):
            captured.update(query)
            return [{"_id": "reported", "sample_oid": "sample-1", "sample": {}}]

    monkeypatch.setattr(
        query_service,
        "enrich_reported_variant_docs",
        lambda docs, **kwargs: docs,
    )
    result = _service(
        variant_repository=SimpleNamespace(get_variant=lambda variant_id: variant),
        reported_variant_repository=Reported(),
    ).tiered_variant_context_payload(variant_id="variant-1", tier=2)
    assert captured["$or"][0].get(expected_key)
    assert result["docs"][0]["sample_id"] == "sample-1"


def test_tiered_search_merges_sources_deduplicates_and_preserves_sample_names() -> None:
    service = _service()
    result = service.tiered_variant_search_payload(
        search_str="TP53",
        search_mode="gene",
        include_annotation_text=True,
        assays=["solid"],
        limit_entries=50,
    )
    assert result["assay_choices"] == ["hematology", "solid"]
    assert result["tier_stats"]["total"] == {"2": 2}
    assert service.annotation_repository.search["asp_ids"] == ["solid"]
    ids = [doc["_id"] for doc in result["docs"]]
    assert "reported-linked" not in ids
    assert ids == ["annotation-1", "reported-direct", "reported-no-text"]
    assert result["docs"][0]["samples"]["sample-1"]["report_oids"] == {"R1": 4}
    assert result["docs"][1]["samples"]["missing-sample"]["sample_name"] == ("preserved-name")
    assert result["docs"][1]["text"] == "text:text-2"
    assert result["docs"][2]["text"] == "matched:reported-no-text"


def test_tiered_search_without_search_uses_all_assays_and_skips_stats() -> None:
    service = _service()
    result = service.tiered_variant_search_payload(
        search_str=None,
        search_mode="all",
        include_annotation_text=False,
        assays=None,
        limit_entries=10,
    )
    assert result["tier_stats"] == {"total": {}, "by_assay": {}}
    assert service.annotation_repository.stats_calls == []
    assert service.annotation_repository.search["asp_ids"] is None
    assert "text" not in result["docs"][-1]
