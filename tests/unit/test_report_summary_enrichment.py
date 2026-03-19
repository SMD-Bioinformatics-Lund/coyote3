from __future__ import annotations

from bson import ObjectId

from api.core.interpretation import report_summary


class _FakeAnnotationCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query):
        wanted = set(query.get("_id", {}).get("$in", []))
        return [doc for doc in self._docs if doc.get("_id") in wanted]


class _FakeAnnotationHandler:
    def __init__(self, docs):
        self._collection = _FakeAnnotationCollection(docs)

    def get_collection(self):
        return self._collection


class _FakeSampleHandler:
    def __init__(self, docs):
        self._docs = docs

    def get_samples_by_oids(self, oids):
        wanted = set(oids)
        return [doc for doc in self._docs if doc.get("_id") in wanted]


class _FakeRepo:
    def __init__(self, sample_docs, annotation_docs):
        self.sample_handler = _FakeSampleHandler(sample_docs)
        self.annotation_handler = _FakeAnnotationHandler(annotation_docs)


def test_enrich_reported_variant_docs_batches_samples_and_annotations(monkeypatch):
    sample_oid = ObjectId()
    annotation_oid = ObjectId()
    docs = [
        {"sample_oid": sample_oid, "annotation_oid": annotation_oid, "tier": 1},
        {"sample_oid": str(sample_oid), "annotation_oid": str(annotation_oid), "tier": 2},
    ]
    sample_docs = [
        {
            "_id": sample_oid,
            "name": "26MD03268",
            "profile": "production",
            "assay": "hematology",
            "subpanel": "Hem",
            "case_id": "case",
            "control_id": "control",
            "paired": True,
        }
    ]
    annotation_docs = [{"_id": annotation_oid, "assay": "hematology", "subpanel": "Hem"}]
    monkeypatch.setattr(
        report_summary, "_core_repo", lambda: _FakeRepo(sample_docs, annotation_docs)
    )

    enriched = report_summary.enrich_reported_variant_docs(docs)

    assert len(enriched) == 2
    assert enriched[0]["sample"]["sample_name"] == "26MD03268"
    assert enriched[0]["annotation"]["assay"] == "hematology"
    assert enriched[1]["sample"]["assay"] == "hematology"
    assert enriched[1]["annotation"]["subpanel"] == "Hem"
