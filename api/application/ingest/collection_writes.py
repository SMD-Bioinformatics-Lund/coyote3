"""Collection-level ingest helpers and contract validation flows."""

from __future__ import annotations

from typing import Any

import yaml  # type: ignore[import-untyped]

from api.application.ingest.helpers import (
    _validate_yaml_manifest_minimum_fields,
    normalize_null_placeholders,
)
from api.application.ingest.parsers import DnaIngestParser, RnaIngestParser, infer_omics_layer
from api.config.contracts.application import PIPELINE_MANIFEST
from api.contracts.schemas.registry import normalize_collection_document, supported_collections
from api.domain.core.internal.results import ReplaceDocumentResult
from api.infra.mongo.persistence import (
    insert_many_documents,
    insert_one_document,
)


def _normalize_pipeline_manifest_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Map supported pipeline field names to the canonical ingest contract."""
    normalized = dict(payload)
    for pipeline_key, canonical_key in PIPELINE_MANIFEST.field_aliases.items():
        if pipeline_key not in normalized:
            continue
        pipeline_value = normalized.pop(pipeline_key)
        canonical_value = normalized.get(canonical_key)
        if (
            canonical_value is not None
            and pipeline_value is not None
            and str(canonical_value).strip() != str(pipeline_value).strip()
        ):
            raise ValueError(
                f"YAML defines conflicting values for '{pipeline_key}' and '{canonical_key}'"
            )
        if canonical_value is None:
            normalized[canonical_key] = pipeline_value
    return normalized


def list_supported_collections() -> list[str]:
    """List collection names that can be validated and inserted by ingest APIs."""
    return supported_collections()


def parse_yaml_payload(yaml_content: str) -> dict[str, Any]:
    """Parse and validate a YAML ingest payload string."""
    parsed = yaml.safe_load(yaml_content)
    if not isinstance(parsed, dict):
        raise ValueError("YAML body must decode to an object")
    parsed = _normalize_pipeline_manifest_fields(normalize_null_placeholders(parsed))
    _validate_yaml_manifest_minimum_fields(parsed)
    return parsed


def parse_preload(service: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Detect omics layer and delegate payload parsing to the appropriate parser."""
    omics_layer = str(args.get("omics_layer") or "").strip().lower()
    if not omics_layer:
        omics_layer = infer_omics_layer(args) or ""
    if omics_layer == "dna":
        hgnc_maps = getattr(service, "_hgnc_metadata_maps", None)
        hgnc_by_id, hgnc_by_symbol = hgnc_maps() if callable(hgnc_maps) else ({}, {})
        return DnaIngestParser(hgnc_by_id=hgnc_by_id, hgnc_by_symbol=hgnc_by_symbol).parse(args)
    if omics_layer == "rna":
        return RnaIngestParser.parse(args)
    raise ValueError("Could not determine data type (DNA/RNA) from payload")


def normalize_collection_docs(collection: str, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of documents through the collection schema contract."""
    return [normalize_collection_document(collection, doc) for doc in docs]


def insert_collection_document(
    service: Any,
    *,
    collection: str,
    document: dict[str, Any],
    ignore_duplicate: bool = False,
) -> dict[str, Any]:
    """Validate and insert one document into a supported collection."""
    normalized_doc = normalize_collection_document(collection, document)
    inserted_id = insert_one_document(
        service._collection(collection),
        dict(normalized_doc),
        ignore_duplicate=ignore_duplicate,
    )
    if inserted_id is None:
        return {"status": "ok", "collection": collection, "inserted_count": 0}
    return {
        "status": "ok",
        "collection": collection,
        "inserted_count": 1,
        "inserted_id": inserted_id,
    }


def insert_collection_documents(
    service: Any,
    *,
    collection: str,
    documents: list[dict[str, Any]],
    ignore_duplicates: bool = False,
) -> dict[str, Any]:
    """Validate and insert many documents into a supported collection."""
    if not documents:
        return {"status": "ok", "collection": collection, "inserted_count": 0}
    normalized_docs = normalize_collection_docs(collection, documents)
    inserted_count = insert_many_documents(
        service._collection(collection),
        [dict(doc) for doc in normalized_docs],
        ignore_duplicates=ignore_duplicates,
    )
    return {
        "status": "ok",
        "collection": collection,
        "inserted_count": inserted_count,
    }


def upsert_collection_document(
    service: Any,
    *,
    collection: str,
    match: dict[str, Any],
    document: dict[str, Any],
    upsert: bool = False,
) -> dict[str, Any]:
    """Validate and replace one document in a supported collection."""
    if not isinstance(match, dict) or not match:
        raise ValueError("match must be a non-empty object")
    normalized_doc = normalize_collection_document(collection, document)
    result = service._collection(collection).replace_one(
        filter=match,
        replacement=dict(normalized_doc),
        upsert=bool(upsert),
    )
    replace_result = ReplaceDocumentResult(
        matched_count=int(result.matched_count or 0),
        modified_count=int(result.modified_count or 0),
        upserted_id=str(result.upserted_id) if result.upserted_id else None,
    )
    return {
        "status": "ok",
        "collection": collection,
        "matched_count": replace_result.matched_count,
        "modified_count": replace_result.modified_count,
        "upserted_id": replace_result.upserted_id,
    }
