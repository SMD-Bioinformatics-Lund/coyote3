"""Dependent-document write helpers for sample ingest workflows."""

from __future__ import annotations

import logging
from typing import Any

from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
)
from api.domain.common.biomarkers import BIOMARKER_FIELDS, biomarker_counts
from api.domain.core.dna.variant_identity import ensure_variant_identity_fields
from api.infra.mongo.persistence import insert_many_documents

logger = logging.getLogger(__name__)


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
        logger.info(
            "Writing annotation vault: documents=%s (transaction pending)", len(anno_vep_docs)
        )
        service.anno_vep_repository.upsert_many(list(anno_vep_docs), session=session)
        logger.info("Annotation vault writes complete (transaction pending)")
    dependent_preload = {
        key: value for key, value in preload.items() if key in INGEST_DEPENDENT_COLLECTIONS
    }
    for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
        if key not in dependent_preload:
            continue

        payload = dependent_preload[key]
        logger.info("Validating and writing %s (transaction pending)", col_name)
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
            logger.info("Wrote %s: documents=1 (transaction pending)", col_name)
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
        logger.info("Wrote %s: documents=%s (transaction pending)", col_name, written[key])
    return written


def data_counts(preload: dict[str, Any]) -> dict[str, int | bool]:
    """Count prepared evidence and each supplied independent measurement analysis.

    Args:
        preload: Parsed evidence keyed by ingest collection payload name.

    Returns:
        Collection counts and lowercase measurement analysis counts. Unprovided
        analyses are absent so an update preserves their previous counts.
    """
    counts = {
        key: (len(preload[key]) if isinstance(preload[key], list) else bool(preload[key]))
        for key in preload
        if key in INGEST_DEPENDENT_COLLECTIONS
    }
    if "biomarkers" in preload:
        measured = preload["biomarkers"]
        counts.update(
            {
                key: value
                for key, value in biomarker_counts([measured]).items()
                if any(field in measured for field in BIOMARKER_FIELDS[key.upper()])
            }
        )
    return counts


def replace_dependents(
    service: Any, *, preload: dict[str, Any], sample_id: str, sample_name: str, session: Any
) -> dict[str, int]:
    """Replace supplied evidence while preserving other measurement analyses.

    Args:
        service: Ingest service with the application collection gateway and writer.
        preload: Parsed and selected incoming evidence.
        sample_id: Parent sample's string identifier.
        sample_name: Parent sample name used by dependent document normalization.
        session: Active required ingest transaction covering reads and all writes.

    Returns:
        Written document counts keyed by ingest payload name.

    Raises:
        ValueError: Multiple existing documents or a conflicting source name require reconciliation.

    Notes:
        Replacing MSI replaces both method fields as one analysis. Absent HRD,
        MSI or TMB input leaves that analysis unchanged.
    """
    sid = str(sample_id)
    if "biomarkers" in preload:
        # Replace only supplied analyses, retaining all other measurements.
        existing = service.collection_gateway.sample_biomarkers(sid, session=session)
        if len(existing) > 1:
            raise ValueError("Multiple biomarker documents require reconciliation before update")
        incoming = preload["biomarkers"]
        merged = dict(existing[0]) if existing else {}
        if merged and merged.get("name") != incoming.get("name"):
            raise ValueError(
                "Biomarker update source name differs from the stored measurement source"
            )
        merged.pop("_id", None)
        for fields in BIOMARKER_FIELDS.values():
            if any(field in incoming for field in fields):
                for field in fields:
                    merged.pop(field, None)
        merged.update(incoming)
        preload = {**preload, "biomarkers": merged}
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
