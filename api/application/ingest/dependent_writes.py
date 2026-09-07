"""Dependent-document write helpers for sample ingest workflows."""

from __future__ import annotations

from typing import Any

from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
)
from api.domain.core.dna.variant_identity import ensure_variant_identity_fields
from api.infra.mongo.persistence import insert_many_documents


def write_dependents(
    service: Any,
    *,
    preload: dict[str, Any],
    sample_id: str,
    sample_name: str,
    session: Any | None = None,
) -> dict[str, int]:
    """Write all dependent analysis documents for a newly created sample."""
    sid = str(sample_id)
    written: dict[str, int] = {}
    anno_vep_docs = preload.get("anno_vep")
    if anno_vep_docs:
        service.anno_vep_repository.upsert_many(list(anno_vep_docs), session=session)
    dependent_preload = {
        key: value for key, value in preload.items() if key in INGEST_DEPENDENT_COLLECTIONS
    }
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key not in dependent_preload:
            continue

        payload = dependent_preload[key]
        if key in INGEST_SINGLE_DOCUMENT_KEYS:
            if not isinstance(payload, dict):
                raise TypeError(f"{key} expected dict, got {type(payload).__name__}")
            doc = dict(payload)
            doc["SAMPLE_ID"] = sid
            if key == "cov":
                doc["sample"] = sample_name
            normalized_doc = service._normalize_collection_docs(col_name, [doc])[0]
            kwargs = {"session": session} if session is not None else {}
            service._collection(col_name).insert_one(dict(normalized_doc), **kwargs)
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
            insert_many_documents(service._collection(col_name), normalized_docs, session=session)
        written[key] = len(normalized_docs)
    return written


def data_counts(preload: dict[str, Any]) -> dict[str, int | bool]:
    """Count documents in each preload data type."""
    return {
        key: (len(preload[key]) if isinstance(preload[key], list) else bool(preload[key]))
        for key in preload
        if key in INGEST_DEPENDENT_COLLECTIONS
    }


def replace_dependents(
    service: Any, *, preload: dict[str, Any], sample_id: str, sample_name: str, session: Any
) -> dict[str, int]:
    """Replace declared evidence within the caller's required transaction."""
    sid = str(sample_id)
    keys_to_replace = set(preload.keys()) & set(INGEST_DEPENDENT_COLLECTIONS)
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key in keys_to_replace:
            service._collection(col_name).delete_many({"SAMPLE_ID": sid}, session=session)
    return service._write_dependents(
        preload=preload,
        sample_id=sample_id,
        sample_name=sample_name,
        session=session,
    )
