"""Validate related legacy sample records and preserve historical reference integrity."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from copy import deepcopy
from typing import Any

from bson import ObjectId, json_util

from api.application.ingest.parsers import _build_anno_vep_docs
from api.domain.core.dna.variant_identity import build_simple_id_hash_from_simple_id
from scripts.upgrade_from_v3.clinical_documents import (
    CLINICAL_COLLECTIONS,
    FINDING_TYPES,
    convert_annotation,
    convert_reported_variant,
    convert_sample,
    extract_comments,
    validate_document,
)


def fingerprint(document: Any) -> str:
    """Hash BSON-aware canonical JSON for comparison without exposing source data.

    Args:
        document: BSON-serializable record or migration plan.

    Returns:
        SHA-256 content digest with stable mapping order.
    """
    payload = json_util.dumps(
        document, sort_keys=True, json_options=json_util.CANONICAL_JSON_OPTIONS
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def build_plan(
    sources: dict[str, list[dict[str, Any]]], sample_metadata: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Convert all selected records and reject missing sample/report references.

    Args:
        sources: Canonical clinical collection names mapped to original records.
        sample_metadata: Explicit canonical metadata indexed by original sample ObjectId text.

    Returns:
        Complete validated destination plan, including extracted comments and reports.

    Raises:
        ValueError: Source scope, identity, metadata, or reference validation fails.
        ValidationError: A record cannot be converted to the current contract.
    """
    if set(sources) - set(CLINICAL_COLLECTIONS):
        raise ValueError("Only application clinical collections may be migrated")
    plan: dict[str, list[dict[str, Any]]] = defaultdict(list)
    samples = {str(row["_id"]): row for row in sources.get("samples", [])}
    if len(samples) != len(sources.get("samples", [])):
        raise ValueError("Duplicate source sample identity")
    if len({sample["name"] for sample in samples.values()}) != len(samples):
        raise ValueError("Duplicate source sample name")
    if set(sample_metadata) - set(samples):
        raise ValueError("Sample metadata includes an unknown source identity")
    for identity, source in samples.items():
        sample, comments, reports = convert_sample(source, sample_metadata.get(identity, {}))
        plan["samples"].append(sample)
        plan["sample_comments"].extend(comments)
        plan["reports"].extend(reports)
    original_variants = {str(row["_id"]): row for row in sources.get("variants", [])}
    if len(original_variants) != len(sources.get("variants", [])):
        raise ValueError("Duplicate source variant identity")
    for collection, documents in sources.items():
        if collection == "samples":
            continue
        for original in documents:
            document = deepcopy(original)
            if collection in FINDING_TYPES:
                sample = samples.get(str(document.get("SAMPLE_ID")))
                if sample is None:
                    raise ValueError("Finding references an absent sample")
                plan["finding_comments"].extend(
                    extract_comments(
                        document, sample=sample, finding_type=FINDING_TYPES[collection]
                    )
                )
            if collection == "variants" and "simple_id_hash" not in document:
                if not document.get("simple_id"):
                    raise ValueError("Variant identity requires explicit reconciliation")
                document["simple_id_hash"] = build_simple_id_hash_from_simple_id(
                    document["simple_id"]
                )
            if collection == "annotation":
                document = convert_annotation(document)
            if collection == "reported_variants" and not document.get("analysis_type"):
                original_variant = original_variants.get(str(document.get("var_oid")))
                if original_variant is None:
                    raise ValueError("Untyped snapshot has no unique original small variant")
                document = convert_reported_variant(document, original_variant)
            plan[collection].append(validate_document(collection, document))
    converted_samples = {str(row["_id"]): row for row in plan["samples"]}
    vault = {}
    for record in plan.get("anno_vep", []):
        key = (record["simple_id_hash"], record["vep_version"])
        if key in vault:
            raise ValueError("Duplicate VEP identity/version in source vault")
        vault[key] = record
    for variant in plan.get("variants", []):
        version = converted_samples[variant["SAMPLE_ID"]].get("database_versions", {}).get("vep")
        if not version:
            raise ValueError("Original VEP version is required to preserve transcript evidence")
        info = variant.get("INFO") or {}
        if not isinstance(info.get("CSQ", []), list) or any(
            not isinstance(row, dict) for row in info.get("CSQ", [])
        ):
            raise ValueError("VEP transcript evidence requires an array of documents")
        for record in _build_anno_vep_docs([variant], version):
            key = (record["simple_id_hash"], record["vep_version"])
            record["_id"] = ObjectId(fingerprint(key)[:24])
            record = validate_document("anno_vep", record)
            existing_vault = vault.get(key)
            if existing_vault:
                if any(
                    existing_vault.get(field) != value
                    for field, value in record.items()
                    if field != "_id"
                ):
                    raise ValueError(
                        "VEP transcript evidence conflicts for the same identity/version"
                    )
                continue
            vault[key] = record
            plan["anno_vep"].append(record)
    by_id = {}
    for collection, documents in plan.items():
        by_id[collection] = {str(document["_id"]): document for document in documents}
        if len(by_id[collection]) != len(documents):
            raise ValueError("Duplicate identity between embedded and standalone records")
    for collection, documents in plan.items():
        for document in documents:
            for key in ("SAMPLE_ID", "sample_oid"):
                if key in document and str(document[key]) not in samples:
                    raise ValueError(f"Orphan {key} reference in {collection}")
            if collection == "reported_variants":
                report = by_id.get("reports", {}).get(str(document["report_oid"]))
                if report is None or str(report["sample_oid"]) != str(document["sample_oid"]):
                    raise ValueError("Reported finding has no matching report/sample")
                if report["report_id"] != document["report_id"]:
                    raise ValueError("Reported finding report identity conflicts")
                for field in ("annotation_oid", "annotation_text_oid"):
                    if document.get(field) is not None and str(document[field]) not in by_id.get(
                        "annotation", {}
                    ):
                        raise ValueError(
                            "Reported finding references an absent clinical annotation"
                        )
            if collection == "finding_comments":
                name = next(
                    key for key, value in FINDING_TYPES.items() if value == document["finding_type"]
                )
                finding = by_id.get(name, {}).get(str(document["finding_oid"]))
                if finding is None or str(finding["SAMPLE_ID"]) != str(document["sample_oid"]):
                    raise ValueError("Comment has no matching finding/sample")
    return dict(plan)
