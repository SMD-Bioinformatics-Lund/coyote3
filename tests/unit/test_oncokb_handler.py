from __future__ import annotations

import httpx
import pytest

from api.application.ingest.oncokb_public import (
    refresh_public_oncokb_gene_cache,
)
from api.infra.knowledgebase.civic import CivicRepository
from api.infra.knowledgebase.oncokb import OnkoKBRepository
from api.infra.knowledgebase.public_oncokb import (
    PublicOncoKbClient,
    analysis_context_from_sample,
    genomic_location_from_variant,
)


class _FakeCollection:
    def __init__(self):
        self.last_query = None

    def find(self, query):
        self.last_query = query
        return [{"Gene": "TP53", "Alteration": "R175H"}]


class _FakeAdapter:
    def __init__(self):
        self.oncokb_collection = _FakeCollection()
        self.oncokb_actionable_collection = _FakeCollection()
        self.oncokb_genes_collection = _FakeCollection()
        self.civic_variants_collection = _FakeCollection()
        self.civic_gene_collection = _FakeCollection()


def test_get_oncokb_action_builds_flat_alteration_list():
    handler = OnkoKBRepository(_FakeAdapter())
    variant = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53"}}}

    rows = handler.get_oncokb_action(variant, ["R175H", "Truncating Mutations"])

    assert rows == [{"Gene": "TP53", "Alteration": "R175H"}]
    assert handler.adapter.oncokb_actionable_collection.last_query == {
        "Gene": "TP53",
        "Alteration": {"$in": ["R175H", "Truncating Mutations", "Oncogenic Mutations"]},
    }


def test_get_civic_data_returns_materialized_documents():
    handler = CivicRepository(_FakeAdapter())
    variant = {
        "CHROM": "17",
        "POS": 7674220,
        "ALT": "T",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSc": "ENST:c.524G>A"}},
    }

    rows = handler.get_civic_data(variant, "NOTHING_IN_HERE")

    assert rows == [{"Gene": "TP53", "Alteration": "R175H"}]
    assert "$or" in handler.get_collection().last_query


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        (
            {"CHROM": "chr7", "POS": 140753336, "REF": "A", "ALT": ["T"]},
            "7,140753336,140753336,A,T",
        ),
        (
            {"CHROM": "1", "POS": 100, "REF": "AT", "ALT": "A"},
            "1,100,101,AT,A",
        ),
    ],
)
def test_public_oncokb_builds_exact_genomic_location(variant, expected):
    assert genomic_location_from_variant(variant) == expected


def test_public_oncokb_requires_complete_genomic_identity():
    assert genomic_location_from_variant({"CHROM": "7", "POS": 140753336}) == ""


def test_public_oncokb_uses_recorded_intents_with_somatic_default():
    assert analysis_context_from_sample({"analysis_intents": ["germline", "somatic", "other"]}) == {
        "analysis_intents": ["germline", "somatic"]
    }
    assert analysis_context_from_sample({}) == {"analysis_intents": ["somatic"]}


def test_public_oncokb_client_queries_exact_genomic_change_per_intent(monkeypatch):
    captured: dict[str, object] = {"requests": []}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"geneExist": True, "variantExist": True, "dataVersion": "public-test"}

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params, headers):
            captured["requests"].append((url, params, headers))
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=2.5)
    result = client.annotate_variant(
        sample={"genome_build": 38, "analysis_intents": ["somatic", "germline"]},
        variant={
            "_id": "v1",
            "CHROM": "7",
            "POS": 140753336,
            "REF": "A",
            "ALT": ["T"],
        },
    )

    assert result["status"] == "ok"
    assert result["source"] == "public.api.oncokb.org"
    assert result["query_method"] == "genomic_change"
    assert result["analysis_context"] == {"analysis_intents": ["germline", "somatic"]}
    assert set(result["responses"]) == {"germline", "somatic"}
    assert all(
        response["dataVersion"] == "public-test" for response in result["responses"].values()
    )
    requests = captured["requests"]
    assert [request[0] for request in requests] == [
        "https://public.api.oncokb.org/api/v1/annotate/germline/mutations/byGenomicChange",
        "https://public.api.oncokb.org/api/v1/annotate/mutations/byGenomicChange",
    ]
    assert all(
        request[1]
        == {
            "referenceGenome": "GRCh38",
            "genomicLocation": "7,140753336,140753336,A,T",
        }
        for request in requests
    )


def test_public_oncokb_client_keeps_intent_failure_explicit(monkeypatch):
    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params, headers):
            if "/germline/" in url:
                raise httpx.ReadTimeout("OncoKB timed out", request=httpx.Request("GET", url))
            return _Response()

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"geneExist": True, "variantExist": True}

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=0.25)

    result = client.annotate_variant(
        sample={"analysis_intents": ["somatic", "germline"]},
        variant={"CHROM": "17", "POS": 7674220, "REF": "C", "ALT": "T"},
    )

    assert result["status"] == "ok"
    assert result["responses"] == {"somatic": {"geneExist": True, "variantExist": True}}
    assert "OncoKB timed out" in result["failures"]["germline"]


def test_public_oncokb_client_fetches_cancer_gene_list(monkeypatch):
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"hugoSymbol": "TP53"}, {"hugoSymbol": "BRAF"}]

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=2.5)

    genes = client.cancer_gene_list()

    assert genes == [{"hugoSymbol": "TP53"}, {"hugoSymbol": "BRAF"}]
    assert captured["url"] == "https://public.api.oncokb.org/api/v1/utils/cancerGeneList"


def test_public_oncokb_client_fetches_all_curated_genes(monkeypatch):
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "hugoSymbol": "TP53",
                    "summary": "TP53 is a tumor suppressor.",
                    "background": "Curated background.",
                }
            ]

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params, headers):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=2.5)

    genes = client.all_curated_genes()

    assert genes[0]["hugoSymbol"] == "TP53"
    assert captured["url"] == "https://public.api.oncokb.org/api/v1/utils/allCuratedGenes"
    assert captured["params"] == {"includeEvidence": "true"}


@pytest.mark.parametrize("method_name", ["cancer_gene_list", "all_curated_genes"])
def test_public_oncokb_catalogue_fetch_rejects_an_invalid_response_shape(monkeypatch, method_name):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"unexpected": "object"}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *_args, **_kwargs):
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1")

    with pytest.raises(ValueError, match="response must be a JSON list"):
        getattr(client, method_name)()


def test_refresh_public_oncokb_gene_cache_matches_the_complete_hgnc_catalogue():
    class _Client:
        def cancer_gene_list(self):
            return [
                {"hugoSymbol": "TP53", "geneAliases": ["P53"], "geneType": "TSG"},
                {"hugoSymbol": "BRAF", "geneAliases": [], "geneType": "ONCOGENE"},
            ]

        def all_curated_genes(self, *, include_evidence):
            assert include_evidence is True
            return [
                {
                    "hugoSymbol": "TP53",
                    "entrezGeneId": 7157,
                    "geneType": "TSG",
                    "summary": "TP53 is a tumor suppressor.",
                    "background": "Curated background.",
                    "setting": "SOMATIC",
                    "highestSensitiveLevel": "LEVEL_1",
                    "highestResistanceLevel": "R1",
                    "grch38RefSeq": "NM_000546.6",
                    "grch38Isoform": "ENST00000269305",
                }
            ]

    class _Cache:
        def __init__(self):
            self.genes = []

        def upsert_gene_markers(self, docs):
            self.genes.extend(docs)
            return len(docs)

        def upsert_cancer_gene_markers(self, docs):
            self.cancer_genes.extend(docs)
            return len(docs)

        def remove_gene_markers_not_in(self, genes):
            self.curated_genes_retained = genes
            return 0

        def remove_cancer_gene_markers_not_in(self, genes):
            self.cancer_genes_retained = genes
            return 0

    class _Hgnc:
        def iter_gene_metadata(self):
            return [
                {
                    "hgnc_id": "HGNC:11998",
                    "hgnc_symbol": "TP53",
                    "prev_symbol": ["P53"],
                    "alias_symbol": [],
                }
            ]

    cache = _Cache()
    cache.cancer_genes = []
    result = refresh_public_oncokb_gene_cache(
        client=_Client(),
        cache_repository=cache,
        hgnc_repository=_Hgnc(),
    )

    assert result == {
        "hgnc_gene_records": 1,
        "hgnc_symbols_indexed": 2,
        "cancer_records_fetched": 2,
        "cancer_records_matched": 1,
        "cancer_genes_upserted": 1,
        "cancer_genes_removed": 0,
        "curated_records_fetched": 1,
        "curated_records_matched": 1,
        "curated_genes_upserted": 1,
        "curated_genes_removed": 0,
    }
    assert cache.cancer_genes[0]["gene"] == "TP53"
    assert cache.genes[0]["gene"] == "TP53"
    assert cache.genes[0]["gene_summary"] == "TP53 is a tumor suppressor."
    assert cache.genes[0]["background"] == "Curated background."
    assert cache.genes[0]["highest_sensitive_level"] == "LEVEL_1"
    assert cache.cancer_genes_retained == {"TP53"}
    assert cache.curated_genes_retained == {"TP53"}


def test_refresh_public_oncokb_gene_cache_requires_local_hgnc_metadata():
    class _Hgnc:
        def iter_gene_metadata(self):
            return []

    with pytest.raises(RuntimeError, match="HGNC catalogue is empty"):
        refresh_public_oncokb_gene_cache(
            client=object(),
            cache_repository=object(),
            hgnc_repository=_Hgnc(),
        )
