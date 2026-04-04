"""Repository contract tests for internal ingest persistence adapters."""

from __future__ import annotations

from types import SimpleNamespace

from bson.objectid import ObjectId

from api.infra.repositories.internal_ingest_mongo import InternalIngestRepository


class _Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self, query=None):
        query = query or {}
        if "name" in query and isinstance(query["name"], str):
            needle = query["name"]
            return [doc for doc in self.docs if doc.get("name") == needle]
        if "name" in query and isinstance(query["name"], dict):
            needle = query["name"].get("$regex", "")
            return [doc for doc in self.docs if needle in doc.get("name", "")]
        if "SAMPLE_ID" in query:
            needle = query["SAMPLE_ID"]
            return [doc for doc in self.docs if doc.get("SAMPLE_ID") == needle]
        if "_id" in query:
            needle = query["_id"]
            return [doc for doc in self.docs if doc.get("_id") == needle]
        return list(self.docs)

    def find_one(self, query, projection=None):
        _ = projection
        matches = self.find(query)
        return matches[0] if matches else None

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("_id", "generated-id"))

    def insert_many(self, docs, ordered=False):
        _ = ordered
        self.docs.extend(dict(doc) for doc in docs)
        return SimpleNamespace(
            inserted_ids=[doc.get("_id", f"id-{idx}") for idx, doc in enumerate(docs)]
        )

    def update_one(self, query, update, upsert=False):
        _ = upsert
        for doc in self.docs:
            if doc.get("_id") == query.get("_id"):
                doc.update(update.get("$set", {}))
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    def replace_one(self, filter, replacement, upsert=False):
        _ = upsert
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in filter.items()):
                self.docs[index] = dict(replacement)
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)
        self.docs.append(dict(replacement))
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id="upserted")

    def delete_one(self, query):
        self.docs = [doc for doc in self.docs if doc.get("_id") != query.get("_id")]

    def delete_many(self, query):
        if "SAMPLE_ID" in query:
            needle = query["SAMPLE_ID"]
            self.docs = [doc for doc in self.docs if doc.get("SAMPLE_ID") != needle]


class _Handler:
    def __init__(self, collection):
        self._collection = collection

    def get_collection(self):
        return self._collection


def test_internal_ingest_repository_contract(monkeypatch):
    existing_id = ObjectId()
    sample_collection = _Collection(
        [
            {"_id": existing_id, "name": "CASE"},
            {"_id": ObjectId(), "name": "CASE-2"},
        ]
    )
    variants_collection = _Collection(
        [{"_id": "v1", "SAMPLE_ID": str(existing_id), "gene": "TP53"}]
    )
    refseq_collection = _Collection([{"gene": "EGFR", "canonical": "NM_005228"}])
    store_stub = SimpleNamespace(
        sample_handler=_Handler(sample_collection),
        coyote_db={
            "refseq_canonical": refseq_collection,
            "variants": variants_collection,
        },
    )
    monkeypatch.setattr("api.infra.repositories.internal_ingest_mongo.store", store_stub)

    repo = InternalIngestRepository()

    assert len(repo.list_samples_by_exact_name("CASE")) == 1
    assert len(repo.list_samples_by_name_pattern("CASE")) == 2
    assert repo.list_refseq_canonical_documents() == [{"gene": "EGFR", "canonical": "NM_005228"}]
    assert repo.find_sample_by_id(str(existing_id))["name"] == "CASE"

    new_sample_id = repo.new_sample_id()
    assert ObjectId.is_valid(new_sample_id)

    inserted_id = repo.insert_sample({"_id": new_sample_id, "name": "NEW"})
    inserted_sample = repo.find_sample_by_id(new_sample_id)
    assert inserted_id == new_sample_id
    assert inserted_sample["name"] == "NEW"
    assert isinstance(inserted_sample["_id"], ObjectId)

    repo.update_sample_fields(new_sample_id, {"status": "ready"})
    assert repo.find_sample_by_id(new_sample_id)["status"] == "ready"

    inserted_variant_id = repo.insert_collection_document(
        "variants",
        {"_id": "v2", "SAMPLE_ID": new_sample_id, "gene": "EGFR"},
    )
    assert inserted_variant_id == "v2"

    inserted_count = repo.insert_collection_documents(
        "variants",
        [
            {"_id": "v3", "SAMPLE_ID": new_sample_id, "gene": "ALK"},
            {"_id": "v4", "SAMPLE_ID": new_sample_id, "gene": "BRAF"},
        ],
    )
    assert inserted_count == 2
    assert len(repo.list_collection_documents("variants", {"SAMPLE_ID": new_sample_id})) == 3

    replace_result = repo.replace_collection_document(
        "variants",
        match={"_id": "v2"},
        document={"_id": "v2", "SAMPLE_ID": new_sample_id, "gene": "ERBB2"},
        upsert=False,
    )
    assert replace_result.matched_count == 1
    assert repo.list_collection_documents("variants", {"SAMPLE_ID": new_sample_id})[0]["gene"] in {
        "TP53",
        "ERBB2",
        "ALK",
        "BRAF",
    }

    repo.delete_collection_documents("variants", {"SAMPLE_ID": new_sample_id})
    assert repo.list_collection_documents("variants", {"SAMPLE_ID": new_sample_id}) == []

    repo.delete_sample(new_sample_id)
    assert repo.find_sample_by_id(new_sample_id) is None
