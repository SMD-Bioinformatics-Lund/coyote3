"""ASP/ASPC-owned file policy validation for sample ingestion."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from api.application.ingest.parsers import infer_omics_layer, runtime_file_path
from api.config.constants import (
    ANALYSIS_FILE_KEYS_BY_OMICS,
    DEFAULT_ENVIRONMENT,
    SAMPLE_FILE_KEYS,
    SUBPANEL_BASE_ID,
    expected_file_keys,
    normalize_clinical_identifier,
    normalize_environment,
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
    panel = panel_collection.find_one({"asp_id": asp_id})
    if not isinstance(panel, dict):
        raise ValueError(f"ASP is not registered for assay '{asp_id}'")
    asp_category = str(panel.get("asp_category") or default_category).strip().lower()
    allowed = set(SAMPLE_FILE_KEYS.get(asp_category, expected_file_keys(default_category)))
    expected = _configured_keys(panel.get("expected_files")) or set(
        expected_file_keys(asp_category)
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
    """Validate ASP/ASPC file requirements and every declared path before parsing."""
    omics = str(payload.get("omics_layer") or infer_omics_layer(payload) or "").lower()
    expected, required = assay_file_policy(
        collection, assay_name=payload.get("asp_id"), omics_layer=omics
    )
    assay = normalize_clinical_identifier(payload.get("asp_id"), label="asp_id")
    environment = normalize_environment(payload.get("environment") or DEFAULT_ENVIRONMENT)
    subpanel = normalize_clinical_identifier(
        payload.get("subpanel_id") or SUBPANEL_BASE_ID, label="subpanel_id"
    )
    query = {"asp_id": assay, "environment": environment, "is_active": True}
    aspc_collection = collection("asp_configs")
    aspc = aspc_collection.find_one({**query, "subpanel_id": subpanel})
    if not isinstance(aspc, dict) and subpanel != SUBPANEL_BASE_ID:
        aspc = aspc_collection.find_one({**query, "subpanel_id": SUBPANEL_BASE_ID})
    if not isinstance(aspc, dict):
        raise ValueError(
            f"No active ASPC is configured for assay='{assay}', subpanel='{subpanel}', "
            f"environment='{environment}'"
        )
    configured = [
        str(value or "").strip().upper()
        for value in aspc.get("analysis_types", [])
        if str(value or "").strip()
    ]
    analysis_map = ANALYSIS_FILE_KEYS_BY_OMICS.get(omics, {})
    configured_keys = {key for analysis in configured for key in analysis_map.get(analysis, ())}
    invalid = sorted(configured_keys - expected)
    if invalid:
        raise ValueError(
            f"ASPC '{aspc.get('aspc_id') or aspc.get('_id')}' enables analyses whose file "
            f"resources are not declared by the ASP: {', '.join(invalid)}"
        )
    required |= configured_keys
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
    if not isinstance(value, list):
        return set()
    return {str(item or "").strip() for item in value if str(item or "").strip()}
