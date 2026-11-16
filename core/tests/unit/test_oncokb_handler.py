from __future__ import annotations

import pytest
from coyote.application.ingest.oncokb_public import refresh_public_oncokb_gene_cache


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

        def refresh_gene_markers(self, cancer_docs, curated_docs):
            return {
                "cancer_genes_upserted": self.upsert_cancer_gene_markers(cancer_docs),
                "curated_genes_upserted": self.upsert_gene_markers(curated_docs),
                "cancer_genes_removed": self.remove_cancer_gene_markers_not_in(
                    {doc["gene"] for doc in cancer_docs}
                ),
                "curated_genes_removed": self.remove_gene_markers_not_in(
                    {doc["gene"] for doc in curated_docs}
                ),
            }

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
