from __future__ import annotations

from api.application.ingest.oncokb_public import (
    enrich_public_oncokb_cache,
    seed_public_oncokb_curated_gene_cache,
)
from api.infra.knowledgebase.civic import CivicRepository
from api.infra.knowledgebase.oncokb import OnkoKBRepository
from api.infra.knowledgebase.public_oncokb import (
    PublicOncoKbClient,
    hgvsg_from_variant,
    normalize_hgvsg_for_oncokb,
    protein_alteration_from_hgvsp,
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


def test_public_oncokb_protein_alteration_from_hgvsp():
    assert protein_alteration_from_hgvsp("ENSP00000269305:p.Arg175His") == "R175H"
    assert protein_alteration_from_hgvsp("p.Val600Glu") == "V600E"


def test_public_oncokb_hgvsg_from_variant_prefers_vep_hgvsg():
    variant = {
        "CHROM": "7",
        "POS": 140753336,
        "REF": "A",
        "ALT": "T",
        "INFO": {"selected_CSQ": {"HGVSg": "7:g.140753336A>T"}},
    }

    assert hgvsg_from_variant(variant) == "7:g.140753336A>T"


def test_public_oncokb_normalizes_hgvsg_prefixes_to_chromosome_label():
    assert normalize_hgvsg_for_oncokb("chr7:g.140453136A>T") == "7:g.140453136A>T"
    assert normalize_hgvsg_for_oncokb("NC_000007.14:g.140453136A>T") == "7:g.140453136A>T"
    assert normalize_hgvsg_for_oncokb("NC_000023.11:g.153296777C>T") == "X:g.153296777C>T"


def test_public_oncokb_hgvsg_from_variant_constructs_simple_snv():
    variant = {
        "CHROM": "chr7",
        "POS": 140753336,
        "REF": "A",
        "ALT": ["T"],
        "INFO": {"selected_CSQ": {}},
    }

    assert hgvsg_from_variant(variant) == "7:g.140753336A>T"


def test_public_oncokb_client_prefers_public_hgvsg(monkeypatch):
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"geneExist": True, "variantExist": True, "dataVersion": "public-test"}]

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=2.5)
    result = client.annotate_variant(
        sample={"genome_build": 38},
        variant={
            "_id": "v1",
            "CHROM": "7",
            "POS": 140753336,
            "REF": "A",
            "ALT": ["T"],
            "INFO": {
                "selected_CSQ": {
                    "SYMBOL": "BRAF",
                    "HGVSp": "ENSP00000288602:p.Val600Glu",
                }
            },
        },
    )

    assert result["status"] == "ok"
    assert result["source"] == "public.api.oncokb.org"
    assert result["query_method"] == "hgvsg"
    assert result["response"]["dataVersion"] == "public-test"
    assert captured["url"] == "https://public.api.oncokb.org/api/v1/annotate/mutations/byHGVSg"
    assert captured["json"][0]["hgvsg"] == "7:g.140753336A>T"
    assert captured["json"][0]["referenceGenome"] == "GRCh38"


def test_public_oncokb_client_falls_back_to_public_protein_change(monkeypatch):
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"geneExist": True, "variantExist": True, "dataVersion": "public-test"}]

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("api.infra.knowledgebase.public_oncokb.httpx.Client", _Client)
    client = PublicOncoKbClient(base_url="https://public.api.oncokb.org/api/v1", timeout=2.5)
    result = client.annotate_variant(
        sample={"genome_build": 38},
        variant={
            "_id": "v1",
            "CHROM": "7",
            "POS": 140753336,
            "REF": "AT",
            "ALT": ["A"],
            "INFO": {
                "selected_CSQ": {
                    "SYMBOL": "BRAF",
                    "HGVSp": "ENSP00000288602:p.Val600Glu",
                }
            },
        },
    )

    assert result["status"] == "ok"
    assert result["query_method"] == "protein_change"
    assert (
        captured["url"] == "https://public.api.oncokb.org/api/v1/annotate/mutations/byProteinChange"
    )
    assert captured["json"][0]["gene"]["hugoSymbol"] == "BRAF"
    assert captured["json"][0]["alteration"] == "V600E"


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


def test_seed_public_oncokb_curated_gene_cache_prefills_gene_summary_collection():
    class _Client:
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

        def public_gene_count(self):
            return 0

        def upsert_gene_markers(self, docs):
            self.genes.extend(docs)
            return len(docs)

    cache = _Cache()
    result = seed_public_oncokb_curated_gene_cache(
        client=_Client(),
        cache_repository=cache,
    )

    assert result == {"fetched": 1, "genes_upserted": 1}
    assert cache.genes[0]["gene"] == "TP53"
    assert cache.genes[0]["gene_summary"] == "TP53 is a tumor suppressor."
    assert cache.genes[0]["background"] == "Curated background."
    assert cache.genes[0]["highest_sensitive_level"] == "LEVEL_1"


def test_public_oncokb_batch_cache_skips_existing_query():
    class _Client:
        @staticmethod
        def build_annotation_query(*, sample, variant):
            return PublicOncoKbClient.build_annotation_query(sample=sample, variant=variant)

        @staticmethod
        def query_hash(query):
            return PublicOncoKbClient.query_hash(query)

        def cancer_gene_list(self):
            return [
                {
                    "hugoSymbol": "TP53",
                    "geneType": "TSG",
                    "oncokbAnnotated": True,
                    "geneAliases": ["P53"],
                    "entrezGeneId": 7157,
                },
                {
                    "hugoSymbol": "BRAF",
                    "geneType": "Oncogene",
                    "oncokbAnnotated": True,
                    "geneAliases": [],
                    "entrezGeneId": 673,
                },
            ]

        def annotate_hgvsgs(self, queries):
            assert len(queries) == 1
            return [
                {
                    "geneExist": True,
                    "variantExist": True,
                    "dataVersion": "public-test",
                    "geneSummary": "BRAF is a kinase.",
                }
            ]

    class _Cache:
        def __init__(self, existing):
            self.existing = existing
            self.annotations = []
            self.genes = []
            self.cancer_genes = [
                {"gene": "TP53", "gene_type": "TSG", "oncokb_annotated": True},
                {"gene": "BRAF", "gene_type": "Oncogene", "oncokb_annotated": True},
            ]

        def public_cancer_gene_count(self):
            return len(self.public_cancer_gene_symbols())

        def public_cancer_gene_symbols(self):
            return {doc["gene"] for doc in self.cancer_genes}

        def existing_query_hashes(self, query_hashes):
            return set(self.existing).intersection(query_hashes)

        def insert_missing_annotations(self, docs):
            self.annotations.extend(docs)
            return len(docs)

        def upsert_gene_markers(self, docs):
            self.genes.extend(docs)
            return len(docs)

        def upsert_cancer_gene_markers(self, docs):
            self.cancer_genes.extend(docs)
            return len(docs)

    sample = {"_id": "s1", "name": "S1", "genome_build": 38}
    existing_variant = {
        "_id": "v-old",
        "CHROM": "17",
        "POS": 7675088,
        "REF": "G",
        "ALT": ["A"],
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSp": "ENSP:p.Arg175His"}},
    }
    new_variant = {
        "_id": "v-new",
        "CHROM": "7",
        "POS": 140753336,
        "REF": "A",
        "ALT": ["T"],
        "INFO": {"selected_CSQ": {"SYMBOL": "BRAF", "HGVSp": "ENSP:p.Val600Glu"}},
    }
    _, existing_query = PublicOncoKbClient.build_annotation_query(
        sample=sample,
        variant=existing_variant,
    )
    cache = _Cache({PublicOncoKbClient.query_hash(existing_query)})

    result = enrich_public_oncokb_cache(
        sample=sample,
        variants=[existing_variant, new_variant],
        client=_Client(),
        cache_repository=cache,
        batch_size=200,
    )

    assert result == {
        "queried": 1,
        "inserted": 1,
        "genes_upserted": 1,
        "skipped": 0,
        "cached": 1,
        "genes_seeded": 0,
    }
    assert cache.annotations[0]["gene"] == "BRAF"
    assert cache.annotations[0]["query_method"] == "hgvsg"
    assert cache.annotations[0]["hgvsg"] == "7:g.140753336A>T"
    assert cache.annotations[0]["variant_ids"] == ["v-new"]
    assert {doc["gene"] for doc in cache.cancer_genes} == {"BRAF", "TP53"}
    assert cache.cancer_genes[0]["gene_type"] == "TSG"
    assert cache.cancer_genes[0]["oncokb_annotated"] is True
    assert cache.genes[-1]["gene"] == "BRAF"
    assert cache.genes[-1]["gene_summary"] == "BRAF is a kinase."
