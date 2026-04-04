"""Mongo repository adapter for internal ingest workflows."""

from __future__ import annotations

from typing import Any

from bson.objectid import ObjectId
from pymongo.errors import BulkWriteError, DuplicateKeyError

from api.core.internal.ports import ReplaceDocumentResult
from api.extensions import store


class InternalIngestRepository:
    """Provide Mongo-backed ingest persistence operations."""

    _handler_map = {
        "variants": "variant_handler",
        "cnvs": "cnv_handler",
        "biomarkers": "biomarker_handler",
        "transloc": "transloc_handler",
        "panel_coverage": "coverage_handler",
        "fusions": "fusion_handler",
        "rna_expression": "rna_expression_handler",
        "rna_classification": "rna_classification_handler",
        "rna_qc": "rna_qc_handler",
    }

    @staticmethod
    def _sample_collection():
        return store.sample_handler.get_collection()

    @classmethod
    def _collection(cls, name: str):
        handler_name = cls._handler_map.get(name)
        if handler_name and hasattr(store, handler_name):
            return getattr(store, handler_name).get_collection()
        return store.coyote_db[name]

    @staticmethod
    def _provider_sample_id(sample_id: str) -> Any:
        if isinstance(sample_id, str) and ObjectId.is_valid(sample_id):
            return ObjectId(sample_id)
        return sample_id

    @classmethod
    def list_samples_by_exact_name(cls, name: str) -> list[dict[str, Any]]:
        """Return samples whose name matches exactly."""
        return list(cls._sample_collection().find({"name": name}))

    @classmethod
    def list_samples_by_name_pattern(cls, name_pattern: str) -> list[dict[str, Any]]:
        """Return samples whose name contains the supplied pattern."""
        return list(cls._sample_collection().find({"name": {"$regex": name_pattern}}))

    @staticmethod
    def list_refseq_canonical_documents() -> list[dict[str, Any]]:
        """Return refseq canonical documents used during ingest parsing."""
        return list(store.coyote_db["refseq_canonical"].find({}))

    @classmethod
    def find_sample_by_name(cls, name: str) -> dict[str, Any] | None:
        """Return one sample document by name."""
        return cls._sample_collection().find_one({"name": name})

    @classmethod
    def find_sample_by_id(cls, sample_id: str) -> dict[str, Any] | None:
        """Return one sample document by id."""
        return cls._sample_collection().find_one({"_id": cls._provider_sample_id(sample_id)})

    @staticmethod
    def new_sample_id() -> str:
        """Return a new provider-native sample id serialized for the app layer."""
        return str(ObjectId())

    @classmethod
    def insert_sample(cls, document: dict[str, Any]) -> str:
        """Insert one sample document and return its stored id."""
        normalized = dict(document)
        if "_id" in normalized:
            normalized["_id"] = cls._provider_sample_id(str(normalized["_id"]))
        result = cls._sample_collection().insert_one(normalized)
        return str(result.inserted_id)

    @classmethod
    def update_sample_fields(cls, sample_id: str, fields: dict[str, Any]) -> None:
        """Apply a partial update to one sample document."""
        cls._sample_collection().update_one(
            {"_id": cls._provider_sample_id(sample_id)},
            {"$set": fields},
            upsert=False,
        )

    @classmethod
    def delete_sample(cls, sample_id: str) -> None:
        """Delete one sample document by id."""
        cls._sample_collection().delete_one({"_id": cls._provider_sample_id(sample_id)})

    @classmethod
    def list_collection_documents(
        cls, collection: str, match: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return documents from a supported ingest collection."""
        return list(cls._collection(collection).find(match))

    @classmethod
    def delete_collection_documents(cls, collection: str, match: dict[str, Any]) -> None:
        """Delete documents from a supported ingest collection."""
        cls._collection(collection).delete_many(match)

    @classmethod
    def insert_collection_document(
        cls, collection: str, document: dict[str, Any], *, ignore_duplicate: bool = False
    ) -> str | None:
        """Insert one document into a supported ingest collection."""
        try:
            result = cls._collection(collection).insert_one(dict(document))
        except DuplicateKeyError:
            if ignore_duplicate:
                return None
            raise
        return str(result.inserted_id)

    @classmethod
    def insert_collection_documents(
        cls,
        collection: str,
        documents: list[dict[str, Any]],
        *,
        ignore_duplicates: bool = False,
    ) -> int:
        """Insert many documents into a supported ingest collection."""
        try:
            result = cls._collection(collection).insert_many(
                [dict(doc) for doc in documents],
                ordered=False,
            )
            return len(result.inserted_ids)
        except BulkWriteError as exc:
            if not ignore_duplicates:
                raise
            details = exc.details or {}
            inserted_count = int(details.get("nInserted", 0))
            write_errors = details.get("writeErrors", []) or []
            non_duplicate_errors = [err for err in write_errors if err.get("code") != 11000]
            if non_duplicate_errors:
                raise
            return inserted_count

    @classmethod
    def replace_collection_document(
        cls,
        collection: str,
        *,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
    ) -> ReplaceDocumentResult:
        """Replace one document in a supported ingest collection."""
        result = cls._collection(collection).replace_one(
            filter=match,
            replacement=dict(document),
            upsert=bool(upsert),
        )
        return ReplaceDocumentResult(
            matched_count=int(result.matched_count or 0),
            modified_count=int(result.modified_count or 0),
            upserted_id=str(result.upserted_id) if result.upserted_id else None,
        )
