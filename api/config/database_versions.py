"""Canonical sample database-version metadata.

Sample manifests and stored sample documents use only the keys defined here.
The VCF-header parser may normalise punctuation and case from external headers,
but API/YAML input must use the canonical keys verbatim.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

SAMPLE_DATABASE_VERSION_LABELS: dict[str, str] = {
    "assembly": "Assembly",
    "clinvar": "ClinVar",
    "cosmic": "COSMIC",
    "dbsnp": "dbSNP",
    "ensembl": "Ensembl",
    "gencode": "GENCODE",
    "genebuild": "Genebuild",
    "gnomad": "gnomAD",
    "hgmd_public": "HGMD Public",
    "polyphen": "PolyPhen",
    "sift": "SIFT",
    "vep": "VEP",
}

SAMPLE_DATABASE_VERSION_KEYS: tuple[str, ...] = tuple(SAMPLE_DATABASE_VERSION_LABELS)
_NULL_VERSION_VALUES = frozenset({"", "null", "none", "nil", "na", "n/a"})


def vep_metadata_release(value: object) -> str:
    """Normalize equivalent VEP metadata release labels without discarding minor releases.

    Args:
        value: Release label such as 113, 113.0, or v113.0.

    Returns:
        The release with a leading v and trailing zero-only components removed.
        A nonzero minor version such as 113.1 remains distinct.
    """
    version = str(value or "").strip().lstrip("vV")
    if re.fullmatch(r"\d+(?:\.\d+)*", version):
        parts = version.split(".")
        while len(parts) > 1 and int(parts[-1]) == 0:
            parts.pop()
        version = ".".join(parts)
    return version


def normalize_database_versions(value: Any) -> dict[str, str]:
    """Validate the canonical sample database-version mapping."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("database_versions must be an object")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        if key not in SAMPLE_DATABASE_VERSION_LABELS:
            raise ValueError(
                "database_versions keys must be one of: " + ", ".join(SAMPLE_DATABASE_VERSION_KEYS)
            )
        if raw_value is None:
            continue
        clean_value = str(raw_value).strip()
        if clean_value.lower() not in _NULL_VERSION_VALUES:
            normalized[key] = clean_value.lstrip("vV") if key == "vep" else clean_value
    return normalized


def canonical_vcf_header_database_version_key(value: object) -> str | None:
    """Map an external VEP-header field spelling to a canonical stored key."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized if normalized in SAMPLE_DATABASE_VERSION_LABELS else None


def sample_vep_version(sample: Mapping[str, Any]) -> str | None:
    """Return VEP metadata from the single canonical sample location."""
    versions = sample.get("database_versions")
    if not isinstance(versions, Mapping):
        return None
    normalized = str(versions.get("vep") or "").strip().lstrip("vV")
    return normalized or None


def require_sample_vep_version(sample: Mapping[str, Any]) -> str:
    """Return a sample-bound VEP version or fail without selecting a fallback."""
    version = sample_vep_version(sample)
    if not version:
        raise ValueError("sample.database_versions.vep is required for DNA operations")
    return version
