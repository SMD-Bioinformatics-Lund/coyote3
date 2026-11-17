# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Portable YAML and file-descriptor normalization at the ingestion boundary."""

from __future__ import annotations

import tomllib
from importlib.resources import files
from typing import Any

import yaml

_DEFAULTS = tomllib.loads(files("coyote.contracts").joinpath("manifest_defaults.toml").read_text())
MANIFEST_FILE_KEYS: dict[str, tuple[str, ...]] = {
    category: tuple(settings["keys"]) for category, settings in _DEFAULTS["files"].items()
}
ALL_MANIFEST_FILE_KEYS = tuple(
    dict.fromkeys(key for keys in MANIFEST_FILE_KEYS.values() for key in keys)
)
_NULL_PLACEHOLDER_STRINGS = frozenset({"", "null", "none", "nil", "na", "n/a"})


def normalize_null_placeholders(value: Any) -> Any:
    """Convert quoted null markers recursively while preserving ordinary values.

    Args:
        value: Parsed YAML scalar, list or mapping.

    Returns:
        A normalized copy; common quoted null markers become None.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return None if stripped.lower() in _NULL_PLACEHOLDER_STRINGS else stripped
    if isinstance(value, dict):
        return {key: normalize_null_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_null_placeholders(item) for item in value]
    return value


def parse_yaml_payload(yaml_content: str) -> dict[str, Any]:
    """Parse the pipeline YAML envelope and canonicalize its declared field names.

    Args:
        yaml_content: YAML text describing one input sample.

    Returns:
        A mapping suitable for SampleManifest or the consuming host's richer schema.

    Raises:
        ValueError: The envelope is not an object, lacks identifying fields, or aliases conflict.
        yaml.YAMLError: The input is invalid YAML.
    """
    parsed = yaml.safe_load(yaml_content)
    if not isinstance(parsed, dict):
        raise ValueError("YAML body must decode to an object")
    normalized = normalize_null_placeholders(parsed)
    for pipeline_key, canonical_key in _DEFAULTS["field_aliases"].items():
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
    if (
        (
            MANIFEST_FILE_KEYS["dna"][0] not in normalized
            or MANIFEST_FILE_KEYS["rna"][0] not in normalized
        )
        and "groups" not in normalized
        and "name" not in normalized
        and "genome_build" not in normalized
    ):
        raise ValueError("YAML is missing mandatory fields: vcf, groups, name or build")
    return normalized


def normalize_manifest_files(data: Any) -> Any:
    """Collect declared file paths and checksums without mutating the caller's input.

    Args:
        data: Manifest mapping or another input for later schema validation.

    Returns:
        A shallow manifest copy with independent file descriptors; other inputs pass through.

    Raises:
        ValueError: Separate biomarker paths are supplied instead of the shared JSON resource.
    """
    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    if any(key in normalized for key in ("hrd", "msi", "tmb")):
        raise ValueError("Use one biomarkers JSON input instead of separate hrd/msi/tmb keys")
    descriptors = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in dict(normalized.get("files") or {}).items()
    }
    for key in ALL_MANIFEST_FILE_KEYS:
        value = normalized.pop(key, None)
        if value:
            descriptors[key] = dict(value) if isinstance(value, dict) else {"path": value}
    checksums = normalized.pop("uploaded_file_checksums", None) or {}
    if isinstance(checksums, dict):
        for key, checksum in checksums.items():
            if key in descriptors and isinstance(descriptors[key], dict):
                descriptors[key].setdefault("checksum", checksum)
    normalized["files"] = descriptors
    return normalized
