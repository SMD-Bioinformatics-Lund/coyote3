"""Collection-level ingest helpers and contract validation flows."""

from __future__ import annotations

from typing import Any

import yaml  # type: ignore[import-untyped]

from api.contracts.schemas.registry import normalize_collection_document, supported_collections
from api.core.internal.results import ReplaceDocumentResult
from api.infra.mongo.persistence import (
    insert_many_documents,
    insert_one_document,
)
from api.services.ingest.helpers import _validate_yaml_payload_like_import_script
from api.services.ingest.parsers import DnaIngestParser, RnaIngestParser, infer_omics_layer


def list_supported_collections() -> list[str]:
    """List collection names that can be validated and inserted by ingest APIs."""
    return supported_collections()


def parse_yaml_payload(yaml_content: str) -> dict[str, Any]:
    """Parse and validate a YAML ingest payload string."""
    parsed = yaml.safe_load(yaml_content)
    if not isinstance(parsed, dict):
        raise ValueError("YAML body must decode to an object")
    _validate_yaml_payload_like_import_script(parsed)
    return parsed


def canonical_map(service: Any) -> dict[str, str]:
    """Build a gene-to-canonical-RefSeq mapping from reference data."""
    mapping: dict[str, str] = {}
    for doc in service.refseq_canonical_collection.find({}):
        gene = doc.get("gene")
        canonical = doc.get("canonical")
        if gene and canonical:
            mapping[gene] = canonical
    return mapping


def parse_preload(service: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Detect omics layer and delegate payload parsing to the appropriate parser."""
    omics_layer = str(args.get("omics_layer") or "").strip().lower()
    if not omics_layer:
        omics_layer = infer_omics_layer(args) or ""
    if omics_layer == "dna":
        return DnaIngestParser(canonical_map(service)).parse(args)
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
