"""Repository contract tests for home/sample persistence adapters."""

from __future__ import annotations

from types import SimpleNamespace

from api.infra.repositories.home_mongo import HomeRepository


class _SampleHandler:
    def __init__(self):
        self.calls = []

    def get_samples(self, **kwargs):
        self.calls.append(("get_samples", kwargs))
        return [{"name": "S1"}]

    def reset_sample_settings(self, sample_id, filters):
        self.calls.append(("reset_sample_settings", sample_id, filters))

    def get_sample(self, sample_id):
        self.calls.append(("get_sample", sample_id))
        return {"_id": sample_id, "name": "S1"}

    def update_sample_filters(self, sample_id, filters):
        self.calls.append(("update_sample_filters", sample_id, filters))

    def get_report(self, sample_id, report_id):
        self.calls.append(("get_report", sample_id, report_id))
        return {"sample_id": sample_id, "report_id": report_id}


class _IsglHandler:
    def get_isgl_by_asp(self, **query):
        return [{"query": query}]

    def get_isgl_by_ids(self, ids):
        return {"ids": ids}


class _AspHandler:
    def get_asp(self, assay):
        return {"asp": assay}

    def get_asp_genes(self, assay):
        return (["TP53", "EGFR"], ["BRCA1"])


class _VariantHandler:
    def __init__(self):
        self.calls = []

    def get_variant_stats(self, sample_id, genes=None):
        self.calls.append((sample_id, genes))
        return {"sample_id": sample_id, "genes": genes}


def test_home_repository_contract(monkeypatch):
    sample_handler = _SampleHandler()
    variant_handler = _VariantHandler()
    store_stub = SimpleNamespace(
        sample_handler=sample_handler,
        isgl_handler=_IsglHandler(),
        asp_handler=_AspHandler(),
        variant_handler=variant_handler,
    )
    monkeypatch.setattr("api.infra.repositories.home_mongo.store", store_stub)

    repo = HomeRepository()

    assert repo.get_samples(
        user_assays=["WGS"],
        user_envs=["production"],
        status="ready",
        report=True,
        search_str="S1",
        limit=10,
        offset=0,
        use_cache=True,
        reload=False,
    ) == [{"name": "S1"}]
    assert sample_handler.calls[0][0] == "get_samples"

    assert repo.get_isgl_by_asp(assay="wgs", is_active=True) == [
        {"query": {"assay": "wgs", "is_active": True}}
    ]
    assert repo.get_isgl_by_ids(["gl1"]) == {"ids": ["gl1"]}
    assert repo.get_asp("wgs") == {"asp": "wgs"}
    assert repo.get_asp_genes("wgs") == (["TP53", "EGFR"], ["BRCA1"])

    repo.reset_sample_settings("S1", {"a": 1})
    assert ("reset_sample_settings", "S1", {"a": 1}) in sample_handler.calls

    assert repo.get_sample("S1") == {"_id": "S1", "name": "S1"}
    assert repo.get_variant_stats("S1") == {"sample_id": "S1", "genes": None}
    assert repo.get_variant_stats("S1", ["TP53"]) == {"sample_id": "S1", "genes": ["TP53"]}

    repo.update_sample_filters("S1", {"max_freq": 0.1})
    assert ("update_sample_filters", "S1", {"max_freq": 0.1}) in sample_handler.calls

    assert repo.get_report("S1", "R1") == {"sample_id": "S1", "report_id": "R1"}
