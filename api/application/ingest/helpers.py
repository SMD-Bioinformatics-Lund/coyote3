"""Sample-name and metadata normalisation helpers for ingest."""

from __future__ import annotations

import shlex
from copy import deepcopy
from typing import Any

from api.config.constants import (
    SAMPLE_DATABASE_VERSION_KEY_ALIASES,
    SUBPANEL_BASE_ID,
    normalize_environment,
)
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.domain.common.assay_filters import format_assay_config

_CASE_CONTROL_KEYS = [
    "case_id",
    "control_id",
    "clarity_control_id",
    "clarity_case_id",
    "clarity_case_pool_id",
    "clarity_control_pool_id",
    "case_ffpe",
    "control_ffpe",
    "case_sequencing_run",
    "control_sequencing_run",
    "case_reads",
    "control_reads",
    "case_purity",
    "control_purity",
]

_NULL_PLACEHOLDER_STRINGS = {"", "null", "none", "nil", "na", "n/a"}


def normalize_null_placeholders(value: Any) -> Any:
    """Convert common string null placeholders to real ``None`` values.

    YAML producers in the historical pipeline sometimes quote nulls, which turns
    them into ordinary strings. The ingest schema needs those placeholders to
    behave like missing values.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in _NULL_PLACEHOLDER_STRINGS:
            return None
        return stripped
    if isinstance(value, dict):
        return {key: normalize_null_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_null_placeholders(item) for item in value]
    return value


def normalize_database_versions(value: Any) -> dict[str, str]:
    """Normalize allowed reference/database version metadata to a string mapping."""
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, raw_value in value.items():
        clean_key = _canonical_database_version_key(key)
        if not clean_key:
            continue
        clean_value = normalize_null_placeholders(raw_value)
        if clean_value is None:
            continue
        normalized[clean_key] = _normalize_database_version_value(clean_key, clean_value)
    return normalized


def _canonical_database_version_key(key: Any) -> str | None:
    clean_key = str(key or "").strip().lower().replace("-", "_").replace(" ", "_")
    clean_key = clean_key.replace(".", "_")
    return SAMPLE_DATABASE_VERSION_KEY_ALIASES.get(clean_key)


def _normalize_database_version_value(key: str, value: Any) -> str:
    clean_value = str(value).strip()
    if key == "vep":
        return clean_value.lstrip("vV")
    return clean_value


def normalize_sample_version_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Fold version aliases and VCF header metadata into canonical sample keys."""
    normalized = dict(payload)
    for alias in ("db_versions", "reference_versions", "annotation_versions"):
        if alias not in normalized:
            continue
        merged_versions = normalize_database_versions(normalized.pop(alias))
        merged_versions.update(normalize_database_versions(normalized.get("database_versions")))
        normalized["database_versions"] = merged_versions

    header_versions = extract_vcf_database_versions(normalized)
    if header_versions:
        merged_versions = header_versions["database_versions"]
        merged_versions.update(normalize_database_versions(normalized.get("database_versions")))
        normalized["database_versions"] = merged_versions
        if not normalized.get("vep_version") and header_versions.get("vep_version"):
            normalized["vep_version"] = header_versions["vep_version"]
    elif "database_versions" in normalized:
        normalized["database_versions"] = normalize_database_versions(
            normalized.get("database_versions")
        )
    return normalized


def extract_vcf_database_versions(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract VEP and annotation database versions from the first VCF header."""
    vcf_path = _sample_path_value(payload, "vcf_files")
    if not vcf_path:
        return {}
    try:
        with open(vcf_path, encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, start=1):
                if line_no > 500:
                    break
                if not line.startswith("##"):
                    if line.startswith("#CHROM"):
                        break
                    continue
                if line.startswith("##VEP="):
                    return _parse_vep_header_line(line.strip())
    except OSError:
        return {}
    return {}


def _parse_vep_header_line(line: str) -> dict[str, Any]:
    raw = line[2:]
    parts = shlex.split(raw)
    versions: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        clean_key = _canonical_database_version_key(key)
        clean_value = value.strip().strip('"')
        if not clean_key or not clean_value:
            continue
        versions[clean_key] = _normalize_database_version_value(clean_key, clean_value)
    vep_raw = versions.get("vep")
    vep_version = vep_raw.lstrip("vV") if vep_raw else None
    if vep_version:
        versions["vep"] = vep_version
    return {"vep_version": vep_version, "database_versions": versions}


def _sample_path_value(payload: dict[str, Any], key: str) -> str | None:
    runtime_files = payload.get("_runtime_files")
    if isinstance(runtime_files, dict) and runtime_files.get(key):
        return str(runtime_files[key])

    files = payload.get("files")
    file_value = files.get(key) if isinstance(files, dict) else None
    if isinstance(file_value, dict):
        path = file_value.get("path")
    else:
        path = file_value or payload.get(key)
    if not path:
        return None
    return str(path)


def _validate_yaml_manifest_minimum_fields(payload: dict[str, Any]) -> None:
    """Validate the minimum fields required for an ingest YAML manifest."""
    if (
        ("vcf_files" not in payload or "fusion_files" not in payload)
        and "groups" not in payload
        and "name" not in payload
        and "genome_build" not in payload
    ):
        raise ValueError("YAML is missing mandatory fields: vcf, groups, name or build")


def _normalize_case_control(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a flat arg dict into case and control sub-dicts, normalising null strings.

    Args:
        args: Raw keyword arguments containing case/control keys.

    Returns:
        A tuple of (case_dict, control_dict) with null strings converted to None.
    """
    normalized = normalize_null_placeholders(args)
    for key in _CASE_CONTROL_KEYS:
        if key in normalized and normalized[key] is None:
            normalized[key] = None

    case: dict[str, Any] = {}
    control: dict[str, Any] = {}
    for key in _CASE_CONTROL_KEYS:
        if "case" in key:
            case[key.replace("case_", "")] = normalized.get(key)
        elif "control" in key:
            control[key.replace("control_", "")] = normalized.get(key)
    return case, control


def build_sample_meta_dict(args: dict[str, Any]) -> dict[str, Any]:
    """Build the top-level sample metadata dict from validated payload args.

    Strips internal operation keys (load, increment, etc.) and promotes
    case/control sub-keys into nested dicts.

    Args:
        args: Validated and dumped sample payload.

    Returns:
        A flat dict suitable for persistence as a sample document.
    """
    sample_dict: dict[str, Any] = {}
    case_dict, control_dict = _normalize_case_control(args)
    blocked = {
        "load",
        "command_selection",
        "debug_logger",
        "quiet",
        "increment",
        "update",
        "dev",
        "_runtime_files",
    }
    normalized_args = normalize_sample_version_metadata(args)
    for key, value in normalized_args.items():
        if key in blocked:
            continue
        if key in _CASE_CONTROL_KEYS and key not in {"case_id", "control_id"}:
            continue
        sample_dict[key] = value

    sample_dict["case"] = case_dict
    if normalized_args.get("control_id"):
        sample_dict["control"] = control_dict
    return sample_dict


def _normalize_uploaded_checksums(payload: Any) -> dict[str, str]:
    """Normalise an uploaded checksums payload to a clean str->str mapping.

    Args:
        payload: Raw checksums value from the ingest request, may be None or non-dict.

    Returns:
        A dict mapping stripped checksum keys to lowercased checksum values.
        Returns an empty dict for any non-dict input.
    """
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in payload.items():
        checksum_key = str(key or "").strip()
        checksum_val = str(value or "").strip().lower()
        if not checksum_key or not checksum_val:
            continue
        normalized[checksum_key] = checksum_val
    return normalized


def assay_default_filters_from_aspc_collection(
    aspc_collection: Any, sample_doc: dict[str, Any]
) -> dict[str, Any] | None:
    """Resolve formatted ASPC default filters and metadata for a sample payload."""
    if aspc_collection is None or not hasattr(aspc_collection, "find_one"):
        return None
    assay_name = str(sample_doc.get("assay") or "").strip()
    subpanel_id = str(sample_doc.get("subpanel_id") or sample_doc.get("subpanel") or "").strip()
    subpanel_id = subpanel_id or SUBPANEL_BASE_ID
    profile = normalize_environment(sample_doc.get("profile") or "production")
    query_base = {
        "asp_id": assay_name,
        "environment": profile,
        "is_active": True,
    }
    raw_config = aspc_collection.find_one({**query_base, "subpanel_id": subpanel_id})
    if not isinstance(raw_config, dict) and subpanel_id != SUBPANEL_BASE_ID:
        raw_config = aspc_collection.find_one({**query_base, "subpanel_id": SUBPANEL_BASE_ID})
    if not isinstance(raw_config, dict):
        return None
    omics = str(sample_doc.get("omics_layer") or "").strip().upper()
    if not omics:
        omics = "RNA" if sample_doc.get("fusion_files") else "DNA"
    schema = build_form_spec(aspc_spec_for_category(omics))
    formatted = format_assay_config(deepcopy(raw_config), schema)
    filters = formatted.get("filters")
    if not isinstance(filters, dict):
        return None
    return {
        "filters": deepcopy(filters),
        "aspc": {
            "_id": raw_config.get("_id"),
            "aspc_id": raw_config.get("aspc_id"),
            "version": raw_config.get("version"),
        },
    }
