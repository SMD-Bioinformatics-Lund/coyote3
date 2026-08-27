"""Sample-update helpers for internal ingest workflows."""

from __future__ import annotations

import re
from typing import Any

from api.application.ingest.parsers import infer_omics_layer
from api.contracts.schemas.samples import DNA_SAMPLE_FILE_KEYS, RNA_SAMPLE_FILE_KEYS


def catch_left_right(case_id: str, name: str) -> tuple[str, str, str]:
    """Extract left and right suffixes relative to a case id inside a sample name."""
    pattern = rf"(.*)({re.escape(case_id)})(.*)"
    match = re.match(pattern, name)
    if not match:
        return "", "", ""
    return match.group(1), match.group(3), match.group(2)


def next_unique_name(service: Any, case_id: str, increment: bool) -> str:
    """Return a unique sample name, optionally auto-suffixing on collision."""
    existing_exact = list(service._sample_collection().find({"name": case_id}))
    if not existing_exact:
        return case_id
    if not increment:
        raise ValueError("Sample already exists; set increment=true to auto-suffix")

    suffixes: list[str] = []
    true_matches = 0
    for doc in service._sample_collection().find({"name": {"$regex": case_id}}):
        left, right, true = catch_left_right(case_id, doc["name"])
        if right and not left and true:
            suffixes.append(right)
            true_matches += 1

    max_suffix = 1
    if true_matches:
        if not suffixes:
            raise ValueError("Multiple exact matches found for sample name")
        for suffix in suffixes:
            match = re.match(r"-\d+", suffix)
            if match:
                number = int(suffix.replace("-", ""))
                if number > max_suffix:
                    max_suffix = number

    return f"{case_id}-{max_suffix + 1}"


def prepare_update_payload(
    service: Any, *, sample_doc: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    """Validate that an update payload preserves the existing omics layer."""
    normalized = dict(payload)
    existing_layer = str(sample_doc.get("omics_layer") or "").strip().lower()
    if existing_layer not in {"dna", "rna"}:
        existing_layer = infer_omics_layer(sample_doc) or ""
    if existing_layer not in {"dna", "rna"}:
        raise ValueError("Cannot determine existing sample data type for update")

    requested_layer = str(normalized.get("omics_layer") or existing_layer).strip().lower()
    if requested_layer != existing_layer:
        raise ValueError(
            f"Sample omics_layer is '{existing_layer}' and cannot be changed to '{requested_layer}'"
        )

    forbidden_keys = RNA_SAMPLE_FILE_KEYS if existing_layer == "dna" else DNA_SAMPLE_FILE_KEYS
    bad_keys = [key for key in forbidden_keys if normalized.get(key)]
    if bad_keys:
        raise ValueError(
            f"Cannot add {'RNA' if existing_layer == 'dna' else 'DNA'} data to an existing {existing_layer.upper()} sample"
        )

    normalized["omics_layer"] = existing_layer
    return normalized


def update_meta_fields(
    service: Any,
    *,
    sample_id: str,
    payload_meta: dict[str, Any],
    block_fields: set[str],
) -> None:
    """Update sample metadata fields while rejecting blocked changes."""
    current = (
        service._sample_collection().find_one({"_id": service._provider_sample_id(sample_id)}) or {}
    )
    update_fields: dict[str, Any] = {}
    for key, value in payload_meta.items():
        if key in {"_id", "name"}:
            continue
        if key in current and current[key] != value:
            if key in block_fields:
                raise ValueError(f"No support to update {key} as of yet")
            update_fields[key] = value
        elif key not in current:
            update_fields[key] = value
    if update_fields:
        service._sample_collection().update_one(
            {"_id": service._provider_sample_id(sample_id)},
            {"$set": update_fields},
            upsert=False,
        )
