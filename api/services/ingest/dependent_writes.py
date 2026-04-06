"""Dependent-document write helpers for sample ingest workflows."""

from __future__ import annotations

from typing import Any

from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
)
from api.core.dna.variant_identity import ensure_variant_identity_fields
from api.infra.mongo.persistence import insert_many_documents


def write_dependents(
    service: Any,
    *,
    preload: dict[str, Any],
    sample_id: str,
    sample_name: str,
) -> dict[str, int]:
    """Write all dependent analysis documents for a newly created sample."""
    sid = str(sample_id)
    written: dict[str, int] = {}
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key not in preload:
            continue

        payload = preload[key]
        if key in INGEST_SINGLE_DOCUMENT_KEYS:
            if not isinstance(payload, dict):
                raise TypeError(f"{key} expected dict, got {type(payload).__name__}")
            doc = dict(payload)
            doc["SAMPLE_ID"] = sid
            if key == "cov":
                doc["sample"] = sample_name
            normalized_doc = service._normalize_collection_docs(col_name, [doc])[0]
            service._collection(col_name).insert_one(dict(normalized_doc))
            written[key] = 1
            continue

        if not isinstance(payload, (list, tuple)):
            raise TypeError(f"{key} expected list, got {type(payload).__name__}")
        docs: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise TypeError(f"{key} contains non-dict item")
            doc = dict(item)
            doc["SAMPLE_ID"] = sid
            if key == "snvs":
                doc = ensure_variant_identity_fields(doc)
            docs.append(doc)
        normalized_docs = service._normalize_collection_docs(col_name, docs)
        if normalized_docs:
            insert_many_documents(service._collection(col_name), normalized_docs)
        written[key] = len(normalized_docs)
    return written


def ingest_dependents(
    service: Any,
    *,
    sample_id: str,
    sample_name: str,
    delete_existing: bool,
    preload: dict[str, Any],
) -> dict[str, int]:
    """Insert dependent analysis payload for an existing sample id."""
    sid = str(sample_id)
    written: dict[str, int] = {}
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key not in preload:
            continue
        if delete_existing:
            service._collection(col_name).delete_many({"SAMPLE_ID": sid})

        raw_payload: Any = preload[key]
        if key in INGEST_SINGLE_DOCUMENT_KEYS:
            if not isinstance(raw_payload, dict):
                raise ValueError(f"{key} expected dict payload")
            doc = dict(raw_payload)
            doc["SAMPLE_ID"] = sid
            if key == "cov":
                doc["sample"] = sample_name
            normalized_doc = service._normalize_collection_docs(col_name, [doc])[0]
            service._collection(col_name).insert_one(dict(normalized_doc))
            written[key] = 1
            continue

        if not isinstance(raw_payload, (list, tuple)):
            raise ValueError(f"{key} expected list payload")
        docs: list[dict[str, Any]] = []
        for item in raw_payload:
            if not isinstance(item, dict):
                raise ValueError(f"{key} contains non-dict item")
            doc = dict(item)
            doc["SAMPLE_ID"] = sid
            if key == "snvs":
                doc = ensure_variant_identity_fields(doc)
            docs.append(doc)
        normalized_docs = service._normalize_collection_docs(col_name, docs)
        if normalized_docs:
            insert_many_documents(service._collection(col_name), normalized_docs)
        written[key] = len(normalized_docs)
    return written


def cleanup(service: Any, sample_id: str) -> None:
    """Roll back a failed ingest by deleting the sample and its dependents."""
    sid = str(sample_id)
    for collection in INGEST_DEPENDENT_COLLECTIONS.values():
        try:
            service._collection(collection).delete_many({"SAMPLE_ID": sid})
        except Exception:
            pass
    try:
        service._sample_collection().delete_one({"_id": service._provider_sample_id(sample_id)})
    except Exception:
        pass


def data_counts(preload: dict[str, Any]) -> dict[str, int | bool]:
    """Count documents in each preload data type."""
    return {
        key: (len(preload[key]) if isinstance(preload[key], list) else bool(preload[key]))
        for key in preload
    }


def snapshot_dependents(
    service: Any, *, sample_id: str, keys: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Back up existing dependent documents before a replacement operation."""
    sid = str(sample_id)
    backup: dict[str, list[dict[str, Any]]] = {}
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key in keys:
            backup[key] = list(service._collection(col_name).find({"SAMPLE_ID": sid}))
    return backup


def restore_dependents(
    service: Any,
    *,
    sample_id: str,
    sample_name: str,
    backup: dict[str, list[dict[str, Any]]],
) -> None:
    """Restore dependent documents from a prior snapshot after a failed replacement."""
    sid = str(sample_id)
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key not in backup:
            continue
        service._collection(col_name).delete_many({"SAMPLE_ID": sid})
        docs = backup[key]
        if docs:
            restored: list[dict[str, Any]] = []
            for doc in docs:
                restored_doc = dict(doc)
                restored_doc.pop("_id", None)
                if key == "cov":
                    restored_doc["sample"] = sample_name
                restored.append(restored_doc)
            insert_many_documents(service._collection(col_name), restored)


def replace_dependents(
    service: Any, *, preload: dict[str, Any], sample_id: str, sample_name: str
) -> dict[str, int]:
    """Atomically replace dependent data with rollback on failure."""
    sid = str(sample_id)
    keys_to_replace = set(preload.keys())
    backup = snapshot_dependents(service, sample_id=sample_id, keys=keys_to_replace)
    try:
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key in keys_to_replace:
                service._collection(col_name).delete_many({"SAMPLE_ID": sid})
        return write_dependents(
            service,
            preload=preload,
            sample_id=sample_id,
            sample_name=sample_name,
        )
    except Exception:
        restore_dependents(
            service,
            sample_id=sample_id,
            sample_name=sample_name,
            backup=backup,
        )
        raise
