"""Common product-level constants used across web, API, and docs."""

from __future__ import annotations

import os
import re
from typing import Iterable

from api.config.assay_groups import ASP_GROUP_OPTIONS
from api.config.clinical_vocabulary import CENTER_CLINICAL_CONTRACT, CLINICAL_VOCABULARY
from api.config.contracts.governance import PERMISSION_CATALOG
from api.config.contracts.ingest import ANALYSIS_PRELOAD_CONTRACT
from api.config.sequencing import PLATFORM_OPTIONS, READ_MODE_OPTIONS

ASP_CATEGORY_OPTIONS: tuple[str, ...] = CENTER_CLINICAL_CONTRACT.vocabulary.assay_categories
ASP_FAMILY_OPTIONS: tuple[str, ...] = CENTER_CLINICAL_CONTRACT.vocabulary.assay_families
SEQUENCING_SCOPE_OPTIONS = CENTER_CLINICAL_CONTRACT.sequencing_scope_options
TARGETED_PANEL_ASP_FAMILY_OPTIONS = CENTER_CLINICAL_CONTRACT.targeted_panel_asp_families

# Expected sample file keys per ASP category.
SAMPLE_FILE_KEYS: dict[str, tuple[str, ...]] = CLINICAL_VOCABULARY.sample_file_keys
ALL_SAMPLE_FILE_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(k for keys in SAMPLE_FILE_KEYS.values() for k in keys)
)

# Required sample file keys default by assay family.
# Centers can narrow/extend this per ASP via `assay_specific_panels.required_files`,
# but these defaults keep the primary assay artefact mandatory out of the box.
REQUIRED_SAMPLE_FILE_KEYS_BY_FAMILY: dict[str, tuple[str, ...]] = (
    CLINICAL_VOCABULARY.required_file_keys_by_family
)

ENVIRONMENT_OPTIONS: tuple[str, ...] = CLINICAL_VOCABULARY.environment_options
DEFAULT_ENVIRONMENT = CLINICAL_VOCABULARY.default_environment

AUTH_PROVIDER_LOCAL = "local"
AUTH_PROVIDER_LDAP = "ldap"


def _auth_provider_options(configured_options: tuple[str, ...]) -> tuple[str, ...]:
    """Apply an optional deployment override to center auth-provider choices.

    ``AUTHENTICATION_PROVIDERS`` is intentionally deployment-scoped: a center
    can keep both providers in its shared vocabulary while enabling only the
    appropriate providers in a particular environment. It accepts a
    comma-separated list of the software-supported providers.
    """
    raw_override = os.getenv("AUTHENTICATION_PROVIDERS", "").strip()
    if not raw_override:
        return configured_options
    providers = tuple(
        dict.fromkeys(part.strip().lower() for part in raw_override.split(",") if part.strip())
    )
    if not providers:
        raise RuntimeError("AUTHENTICATION_PROVIDERS must contain at least one provider")
    allowed = {AUTH_PROVIDER_LOCAL, AUTH_PROVIDER_LDAP}
    invalid = set(providers) - allowed
    if invalid:
        raise RuntimeError(
            "AUTHENTICATION_PROVIDERS contains unsupported provider(s): "
            + ", ".join(sorted(invalid))
        )
    return providers


AUTH_TYPE_OPTIONS: tuple[str, ...] = _auth_provider_options(CLINICAL_VOCABULARY.auth_type_options)
DEFAULT_AUTH_PROVIDER = (
    AUTH_PROVIDER_LDAP if AUTH_PROVIDER_LDAP in AUTH_TYPE_OPTIONS else AUTH_TYPE_OPTIONS[0]
)

DNA_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = tuple(
    CLINICAL_VOCABULARY.analysis_file_keys_by_omics["dna"]
)

RNA_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = tuple(
    CLINICAL_VOCABULARY.analysis_file_keys_by_omics["rna"]
)

ALL_ANALYSIS_TYPE_OPTIONS: tuple[str, ...] = tuple(
    dict.fromkeys(DNA_ANALYSIS_TYPE_OPTIONS + RNA_ANALYSIS_TYPE_OPTIONS)
)

ANALYSIS_FILE_KEYS_BY_OMICS: dict[str, dict[str, tuple[str, ...]]] = (
    CLINICAL_VOCABULARY.analysis_file_keys_by_omics
)


def analysis_file_keys(omics_layer: object, analysis_type: object) -> tuple[str, ...]:
    """Return the configured manifest file keys for an implemented analysis."""
    category = normalize_asp_category(omics_layer)
    analysis = str(analysis_type or "").strip().upper()
    try:
        return ANALYSIS_FILE_KEYS_BY_OMICS[category][analysis]
    except KeyError as error:
        raise ValueError(f"analysis '{analysis}' is not configured for {category}") from error


def primary_analysis_file_key(omics_layer: object, analysis_type: object) -> str:
    """Return the primary configured manifest file key for an analysis."""
    return analysis_file_keys(omics_layer, analysis_type)[0]


def analysis_type_for_file_key(omics_layer: object, file_key: object) -> str:
    """Return the configured analysis type that owns a manifest file key."""
    category = normalize_asp_category(omics_layer)
    normalized_key = str(file_key or "").strip()
    for analysis_type, keys in ANALYSIS_FILE_KEYS_BY_OMICS[category].items():
        if normalized_key in keys:
            return analysis_type
    raise ValueError(f"file key '{normalized_key}' is not configured for {category}")


def manifest_file_preload_keys(omics_layer: object) -> dict[str, str]:
    """Map configured manifest file keys to their database preload payloads.

    The configuration owns external manifest names. The application owns the
    parser payload names because they are tied to collection contracts.
    """
    category = normalize_asp_category(omics_layer)
    configured = ANALYSIS_FILE_KEYS_BY_OMICS[category]
    bindings = ANALYSIS_PRELOAD_CONTRACT.preload_keys_by_omics.get(category, {})
    missing = set(configured) - set(bindings)
    if missing:
        raise RuntimeError(
            f"Missing ingest preload binding(s) for {category}: " + ", ".join(sorted(missing))
        )

    result: dict[str, str] = {}
    for analysis_type, file_keys in configured.items():
        preload_key = bindings[analysis_type]
        if preload_key is None:
            continue
        for file_key in file_keys:
            existing = result.setdefault(file_key, preload_key)
            if existing != preload_key:
                raise RuntimeError(
                    f"Configured file key {file_key!r} has incompatible ingest payload bindings "
                    f"({existing!r}, {preload_key!r})"
                )
    return result


def non_database_manifest_file_keys(omics_layer: object) -> frozenset[str]:
    """Return configured file keys that intentionally do not write a collection."""
    category = normalize_asp_category(omics_layer)
    bindings = ANALYSIS_PRELOAD_CONTRACT.preload_keys_by_omics.get(category, {})
    return frozenset(
        file_key
        for analysis_type, file_keys in ANALYSIS_FILE_KEYS_BY_OMICS[category].items()
        if bindings.get(analysis_type) is None
        for file_key in file_keys
    )


GENELIST_STANDARD_TYPE_OPTIONS: tuple[str, ...] = CLINICAL_VOCABULARY.genelist_standard_types
GENELIST_ADHOC_TYPE_OPTIONS: tuple[str, ...] = CLINICAL_VOCABULARY.genelist_adhoc_types

GENELIST_TYPE_OPTIONS: tuple[str, ...] = (
    *GENELIST_STANDARD_TYPE_OPTIONS,
    *GENELIST_ADHOC_TYPE_OPTIONS,
)

# ASPC reporting is a clinical contract. These fields are the minimum authored
# configuration required before an active configuration may generate a report.
ASPC_REQUIRED_REPORTING_FIELDS: tuple[str, ...] = CLINICAL_VOCABULARY.required_aspc_reporting_fields
TRANSCRIPT_SELECTION_ORDER: tuple[str, ...] = CLINICAL_VOCABULARY.transcript_selection_order
SUBPANEL_BASE_ID = CLINICAL_VOCABULARY.base_subpanel_id

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_identifier(value: object, *, label: str = "identifier") -> str:
    """Validate an identifier: preserve case, allow alphanumeric, underscore, and hyphen."""
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    if not _IDENTIFIER_RE.match(normalized):
        raise ValueError(
            f"{label} must contain only letters, digits, underscores, and hyphens "
            f"(got {normalized!r})"
        )
    return normalized


def normalize_clinical_identifier(value: object, *, label: str = "identifier") -> str:
    """Return the canonical lower-case form of a clinical identifier.

    ASP, ASPC, ISGL, and subpanel identifiers are join keys across MongoDB,
    static reporting rules, manifests, and access scope. They are therefore
    case-insensitive identifiers, unlike human-facing display labels. Hyphens
    and underscores are meaningful accepted separators and are preserved;
    whitespace, dots, and every other unsupported character are rejected at
    the boundary rather than silently rewritten.
    """
    normalized = str(value or "").strip().lower()
    return validate_identifier(normalized, label=label)


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
    return _ensure_in_options(value, options=ASP_CATEGORY_OPTIONS, label="asp_category")


def normalize_environment(value: object, *, label: str = "environment") -> str:
    """Normalize and validate environment/profile values."""
    return _ensure_in_options(value, options=ENVIRONMENT_OPTIONS, label=label)


def normalize_auth_type(value: object) -> str:
    """Normalize and validate an auth type."""
    return _ensure_in_options(value, options=AUTH_TYPE_OPTIONS, label="auth_type")


def normalize_auth_types(value: object) -> list[str]:
    """Normalize and validate a user auth-provider list."""
    if value is None:
        return [DEFAULT_AUTH_PROVIDER]
    if isinstance(value, (str, bytes)):
        raw_values = [value]
    else:
        try:
            raw_values = list(value)  # type: ignore[arg-type]
        except TypeError:
            raw_values = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        provider = normalize_auth_type(item)
        if provider not in seen:
            normalized.append(provider)
            seen.add(provider)
    return normalized or [DEFAULT_AUTH_PROVIDER]


def normalize_platform(value: object) -> str | None:
    """Normalize and validate a sequencing platform."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return _ensure_in_options(normalized, options=PLATFORM_OPTIONS, label="platform")


def normalize_read_mode(value: object) -> str | None:
    """Normalize and validate sequencing read mode."""
    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    return _ensure_in_options(
        normalized,
        options=READ_MODE_OPTIONS,
        label="read_mode",
        lowercase=False,
    )


def normalize_analysis_type(value: object) -> str:
    """Validate a canonical analysis type."""
    normalized = str(value or "").strip().upper()
    return _ensure_in_options(
        normalized,
        options=ALL_ANALYSIS_TYPE_OPTIONS,
        label="analysis_type",
        lowercase=False,
    )


def normalize_genelist_type(value: object) -> str:
    """Normalize and validate an in-silico genelist type."""
    normalized = str(value or "").strip().lower()
    return _ensure_in_options(
        normalized,
        options=GENELIST_TYPE_OPTIONS,
        label="list_type",
    )


def normalize_permission_category(value: object) -> str:
    """Normalize and validate a permission category label."""
    normalized = str(value or "").strip()
    if normalized not in PERMISSION_CATALOG.categories:
        raise ValueError(
            "permission category must be one of: " + ", ".join(PERMISSION_CATALOG.categories)
        )
    return normalized


def normalize_sequencing_scope(value: object) -> str:
    """Normalize and validate a sequencing scope."""
    return _ensure_in_options(value, options=SEQUENCING_SCOPE_OPTIONS, label="sequencing_scope")


def scope_from_family(asp_family: str) -> str:
    """Derive the sequencing scope from an ASP family value."""
    normalized = normalize_asp_family(asp_family)
    return CLINICAL_VOCABULARY.assay_family_scopes[normalized]


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
    category = normalize_asp_category(asp_category or ASP_CATEGORY_OPTIONS[0])
    configured_analyses = tuple(ANALYSIS_FILE_KEYS_BY_OMICS.get(category, {}))
    if not configured_analyses:
        return ()
    return (primary_analysis_file_key(category, configured_analyses[0]),)


# User-selectable table sizes are bounded to protect browser rendering and
# database queries while still supporting compact and high-density workflows.
TABLE_PAGE_SIZE_OPTIONS: tuple[int, ...] = (25, 50, 100, 200)
DEFAULT_TABLE_PAGE_SIZE = 50
