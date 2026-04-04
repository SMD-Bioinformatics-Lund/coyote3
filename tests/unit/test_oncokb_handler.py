from __future__ import annotations

from api.infra.knowledgebase.civic import CivicHandler
from api.infra.knowledgebase.oncokb import OnkoKBHandler


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
    handler = OnkoKBHandler(_FakeAdapter())
    variant = {"INFO": {"selected_CSQ": {"SYMBOL": "TP53"}}}

    rows = handler.get_oncokb_action(variant, ["R175H", "Truncating Mutations"])

    assert rows == [{"Gene": "TP53", "Alteration": "R175H"}]
    assert handler.adapter.oncokb_actionable_collection.last_query == {
        "Gene": "TP53",
        "Alteration": {"$in": ["R175H", "Truncating Mutations", "Oncogenic Mutations"]},
    }


def test_get_civic_data_returns_materialized_documents():
    handler = CivicHandler(_FakeAdapter())
    variant = {
        "CHROM": "17",
        "POS": 7674220,
        "ALT": "T",
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53", "HGVSc": "ENST:c.524G>A"}},
    }

    rows = handler.get_civic_data(variant, "NOTHING_IN_HERE")

    assert rows == [{"Gene": "TP53", "Alteration": "R175H"}]
    assert "$or" in handler.get_collection().last_query
