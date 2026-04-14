"""Shared product-level constants used across web, API, and docs."""

from __future__ import annotations

import re
from typing import Iterable

ASP_GROUP_OPTIONS: tuple[str, ...] = (
    "hematology",
    "solid",
    "pgx",
    "tumwgs",
    "wts",
    "myeloid",
    "lymphoid",
)

ASP_CATEGORY_OPTIONS: tuple[str, ...] = ("dna", "rna")

ASP_FAMILY_OPTIONS: tuple[str, ...] = (
    "panel-dna",
    "panel-rna",
    "wgs",
    "wts",
)

# Sequencing scope is derived from family: "panel-dna"/"panel-rna" → "panel", others as-is.
SEQUENCING_SCOPE_OPTIONS: tuple[str, ...] = tuple(
    dict.fromkeys("panel" if f.startswith("panel-") else f for f in ASP_FAMILY_OPTIONS)
)

# Expected sample file keys per ASP category.
SAMPLE_FILE_KEYS: dict[str, tuple[str, ...]] = {
    "dna": (
        "vcf_files",
        "cnv",
        "cnvprofile",
        "cov",
        "transloc",
        "biomarkers",
    ),
    "rna": (
        "fusion_files",
        "expression_path",
        "classification_path",
        "qc",
    ),
}
ALL_SAMPLE_FILE_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(k for keys in SAMPLE_FILE_KEYS.values() for k in keys)
)

# Required sample file keys default by assay family.
# Centers can narrow/extend this per ASP via `assay_specific_panels.required_files`,
# but these defaults keep the primary assay artefact mandatory out of the box.
REQUIRED_SAMPLE_FILE_KEYS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "panel-dna": ("vcf_files",),
    "wgs": ("vcf_files",),
    "panel-rna": ("fusion_files",),
    "wts": ("fusion_files",),
}

ENVIRONMENT_OPTIONS: tuple[str, ...] = (
    "production",
    "development",
    "testing",
    "validation",
)

AUTH_TYPE_OPTIONS: tuple[str, ...] = ("coyote3", "ldap")

PLATFORM_OPTIONS: tuple[str, ...] = (
    "illumina",
    "pacbio",
    "nanopore",
    "iontorrent",
)

DNA_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = (
    "SNV",
    "CNV",
    "TRANSLOCATION",
    "BIOMARKER",
    "CNV_PROFILE",
    "FUSION",
    "TMB",
    "PGX",
)

RNA_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = (
    "FUSION",
    "EXPRESSION",
    "CLASSIFICATION",
    "QC",
    "PGX",
)

ALL_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = tuple(
    dict.fromkeys(DNA_ANALYSIS_TYPE_OPTIONS + RNA_ANALYSIS_TYPE_OPTIONS)
)

PERMISSION_CATEGORY_OPTIONS: tuple[str, ...] = (
    "Analysis Actions",
    "Assay Configuration Management",
    "Assay Panel Management",
    "Audit & Monitoring",
    "Data Downloads",
    "Gene List Management",
    "Permission Policy Management",
    "Reports",
    "Role Management",
    "Sample Management",
    "Schema Management",
    "User Management",
    "Variant Curation",
    "Visualization",
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")


def validate_identifier(value: object, *, label: str = "identifier") -> str:
    """Validate an identifier: preserve case, allow only alphanumeric and underscore, no spaces."""
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    if not _IDENTIFIER_RE.match(normalized):
        raise ValueError(
            f"{label} must contain only letters, digits, and underscores (got {normalized!r})"
        )
    return normalized


def _ensure_in_options(
    value: object,
    *,
    options: Iterable[str],
    label: str,
    lowercase: bool = True,
) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.lower() if lowercase else normalized
    allowed = tuple(options)
    if normalized not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
    return normalized


def normalize_asp_group(value: object) -> str:
    """Normalize and validate an ASP group identifier."""
    return _ensure_in_options(value, options=ASP_GROUP_OPTIONS, label="asp_group")


def normalize_asp_family(value: object) -> str:
    """Normalize and validate an ASP family identifier."""
    return _ensure_in_options(value, options=ASP_FAMILY_OPTIONS, label="asp_family")


def normalize_asp_category(value: object) -> str:
    """Normalize and validate an ASP category identifier."""
    aliases = {"somatic": "dna", "dna": "dna", "rna": "rna"}
    normalized = aliases.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    return _ensure_in_options(normalized, options=ASP_CATEGORY_OPTIONS, label="asp_category")


def normalize_environment(value: object, *, label: str = "environment") -> str:
    """Normalize and validate environment/profile values."""
    aliases = {
        "prod": "production",
        "p": "production",
        "production": "production",
        "dev": "development",
        "d": "development",
        "development": "development",
        "test": "testing",
        "t": "testing",
        "testing": "testing",
        "validation": "validation",
        "stage": "validation",
        "staging": "validation",
        "v": "validation",
    }
    normalized = aliases.get(str(value or "").strip().lower())
    if normalized is None:
        raise ValueError(f"{label} must be one of: {', '.join(ENVIRONMENT_OPTIONS)}")
    return normalized


def normalize_auth_type(value: object) -> str:
    """Normalize and validate an auth type."""
    return _ensure_in_options(value, options=AUTH_TYPE_OPTIONS, label="auth_type")


def normalize_platform(value: object) -> str | None:
    """Normalize and validate a sequencing platform."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return _ensure_in_options(normalized, options=PLATFORM_OPTIONS, label="platform")


def normalize_permission_category(value: object) -> str:
    """Normalize and validate a permission category label."""
    normalized = str(value or "").strip()
    if normalized not in PERMISSION_CATEGORY_OPTIONS:
        raise ValueError(
            "permission category must be one of: " + ", ".join(PERMISSION_CATEGORY_OPTIONS)
        )
    return normalized


def normalize_sequencing_scope(value: object) -> str:
    """Normalize and validate a sequencing scope."""
    return _ensure_in_options(value, options=SEQUENCING_SCOPE_OPTIONS, label="sequencing_scope")


def scope_from_family(asp_family: str) -> str:
    """Derive the sequencing scope from an ASP family value."""
    normalized = str(asp_family or "").strip().lower()
    if normalized.startswith("panel-"):
        return "panel"
    return normalize_sequencing_scope(normalized)


def expected_file_keys(asp_category: str) -> tuple[str, ...]:
    """Return the expected sample file keys for an ASP category."""
    normalized = normalize_asp_category(asp_category)
    return SAMPLE_FILE_KEYS.get(normalized, ())


def required_file_keys(
    *, asp_family: object | None = None, asp_category: object | None = None
) -> tuple[str, ...]:
    """Return the default required sample file keys for an assay family/category."""
    family = str(asp_family or "").strip().lower()
    if family in REQUIRED_SAMPLE_FILE_KEYS_BY_FAMILY:
        return REQUIRED_SAMPLE_FILE_KEYS_BY_FAMILY[family]
    category = normalize_asp_category(asp_category or "dna")
    if category == "rna":
        return ("fusion_files",)
    return ("vcf_files",)
