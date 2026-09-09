"""ASP/ASPC-owned file policy validation for sample ingestion."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from api.application.ingest.parsers import infer_omics_layer, runtime_file_path
from api.config.constants import (
    SAMPLE_FILE_KEYS,
    expected_file_keys,
    normalize_clinical_identifier,
)
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS

CollectionResolver = Callable[[str], Any]


def assay_file_policy(
    collection: CollectionResolver,
    *,
    assay_name: str | None,
    omics_layer: str | None,
) -> tuple[set[str], set[str]]:
    """Return ASP-controlled expected and required file keys for an assay."""
    normalized_omics = str(omics_layer or "").strip().lower()
    default_category = "rna" if normalized_omics == "rna" else "dna"
    if not assay_name:
        raise ValueError("assay is required for sample ingest")
    asp_id = normalize_clinical_identifier(assay_name, label="asp_id")
    panel_collection = collection("assay_specific_panels")
    if not hasattr(panel_collection, "find_one"):
        raise ValueError("assay_specific_panels collection is not available for sample ingest")
    panel = panel_collection.find_one({"asp_id": asp_id, "is_active": True})
    if not isinstance(panel, dict):
        raise ValueError(f"No active ASP is configured for assay '{asp_id}'")
    asp_category = str(panel.get("asp_category") or default_category).strip().lower()
    allowed = set(SAMPLE_FILE_KEYS.get(asp_category, expected_file_keys(default_category)))
    expected = (
        _configured_keys(panel["expected_files"])
        if "expected_files" in panel
        else set(expected_file_keys(asp_category))
    )
    required = _configured_keys(panel.get("required_files"))
    invalid_required = required - expected
    if invalid_required:
        raise ValueError(
            f"ASP '{assay_name}' has required_files outside expected_files: {sorted(invalid_required)}"
        )
    return expected & allowed, required & allowed


def validate_payload_file_keys(
    collection: CollectionResolver, payload: dict[str, Any]
) -> dict[str, Any]:
    """Reject declared file resources outside the active ASP contract."""
    validated = dict(payload)
    omics_layer = (
        str(validated.get("omics_layer") or infer_omics_layer(validated) or "").strip().lower()
    )
    expected, _required = assay_file_policy(
        collection, assay_name=validated.get("asp_id"), omics_layer=omics_layer
    )
    files = validated.get("files") if isinstance(validated.get("files"), dict) else {}
    runtime = (
        validated.get("_runtime_files") if isinstance(validated.get("_runtime_files"), dict) else {}
    )
    declared = {
        key
        for key in SAMPLE_SOURCE_PATH_KEYS
        if validated.get(key) or files.get(key) or runtime.get(key)
    }
    unexpected = sorted(declared - expected)
    if unexpected:
        raise ValueError(
            f"ASP '{validated.get('asp_id')}' does not accept declared ingest file(s): "
            + ", ".join(unexpected)
        )
    return validated


def validate_declared_file_resources(
    collection: CollectionResolver, payload: dict[str, Any]
) -> set[str]:
    """Validate only active ASP file requirements and declared paths before parsing."""
    omics = str(payload.get("omics_layer") or infer_omics_layer(payload) or "").lower()
    expected, required = assay_file_policy(
        collection, assay_name=payload.get("asp_id"), omics_layer=omics
    )
    declared = {key for key in expected if runtime_file_path(payload, key)}
    missing = sorted(required - declared)
    if missing:
        raise ValueError(
            f"Missing required ingest file(s) for assay '{payload.get('asp_id')}': {', '.join(missing)}"
        )
    unreadable = sorted(
        key for key in declared if not os.path.exists(str(runtime_file_path(payload, key) or ""))
    )
    if unreadable:
        details = ", ".join(f"{key}={runtime_file_path(payload, key)}" for key in unreadable)
        raise FileNotFoundError(f"Declared ingest file(s) are not readable: {details}")
    return declared


def _configured_keys(value: Any) -> set[str]:
    """Collect distinct nonblank file-resource keys from list-shaped configuration.

    Args:
        value: Configured key list; other shapes are ignored.

    Returns:
        Stripped string keys excluding falsey entries, or an empty set for non-lists.
    """
    if not isinstance(value, list):
        return set()
    return {str(item or "").strip() for item in value if str(item or "").strip()}
