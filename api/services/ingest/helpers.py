"""Sample-name and metadata normalisation helpers for ingest."""

from __future__ import annotations

from typing import Any

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


def _validate_yaml_payload_like_import_script(payload: dict[str, Any]) -> None:
    """Mirror `scripts/import_coyote_sample.py::validate_yaml` mandatory-field guard."""
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
    normalized = dict(args)
    for key in _CASE_CONTROL_KEYS:
        if key in normalized and (normalized[key] is None or normalized[key] == "null"):
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
        A flat dict suitable for MongoDB insertion as a samples document.
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
    for key, value in args.items():
        if key in blocked:
            continue
        if key in _CASE_CONTROL_KEYS and key not in {"case_id", "control_id"}:
            continue
        sample_dict[key] = value

    sample_dict["case"] = case_dict
    if args.get("control_id"):
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
