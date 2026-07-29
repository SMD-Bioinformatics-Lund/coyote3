"""Load the center-owned clinical vocabulary contract.

The vocabulary contains only center-owned choices. Data-model semantics,
analysis capability, and operational profiles remain application contracts in
``constants``.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.config.paths import CLINICAL_VOCABULARY_PATH

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SOFTWARE_AUTH_PROVIDERS = frozenset({"local", "ldap"})


@dataclass(frozen=True)
class ClinicalVocabulary:
    """Validated center-owned selectable values used by the application."""

    assay_categories: tuple[str, ...]
    assay_families: tuple[str, ...]
    assay_family_categories: dict[str, str]
    assay_family_scopes: dict[str, str]
    base_subpanel_id: str
    environment_options: tuple[str, ...]
    default_environment: str
    platforms: tuple[str, ...]
    read_modes: tuple[str, ...]
    sample_file_keys: dict[str, tuple[str, ...]]
    required_file_keys_by_family: dict[str, tuple[str, ...]]
    analysis_file_keys_by_omics: dict[str, dict[str, tuple[str, ...]]]
    auth_type_options: tuple[str, ...]
    genelist_standard_types: tuple[str, ...]
    genelist_adhoc_types: tuple[str, ...]
    required_aspc_reporting_fields: tuple[str, ...]
    permission_categories: tuple[str, ...]


def _string_tuple(
    raw: Any,
    *,
    key: str,
    uppercase: bool = False,
    lowercase: bool = True,
) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"clinical vocabulary key '{key}' must be a non-empty array")
    values = tuple(
        str(value).strip().upper()
        if uppercase
        else str(value).strip().lower()
        if lowercase
        else str(value).strip()
        for value in raw
    )
    if any(not value for value in values) or len(set(values)) != len(values):
        raise RuntimeError(f"clinical vocabulary key '{key}' must contain unique non-empty values")
    return values


def _identifier_tuple(raw: Any, *, key: str) -> tuple[str, ...]:
    values = _string_tuple(raw, key=key)
    invalid = [value for value in values if not _IDENTIFIER_RE.fullmatch(value)]
    if invalid:
        raise RuntimeError(
            f"clinical vocabulary key '{key}' contains invalid identifiers: {', '.join(invalid)}"
        )
    return values


def _identifier_value(raw: Any, *, key: str) -> str:
    """Validate one required identifier value."""
    if not isinstance(raw, str):
        raise RuntimeError(f"clinical vocabulary key '{key}' must be a non-empty string")
    return _identifier_tuple([raw], key=key)[0]


def load_clinical_vocabulary(path: str | Path = CLINICAL_VOCABULARY_PATH) -> ClinicalVocabulary:
    """Load and validate the required center-owned TOML vocabulary."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise RuntimeError(f"clinical vocabulary configuration does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw = tomllib.load(handle)

    assay = raw.get("assay")
    environment = raw.get("environment")
    sequencing = raw.get("sequencing")
    files = raw.get("files")
    analysis = raw.get("analysis")
    authentication = raw.get("authentication")
    genelist = raw.get("genelist")
    reporting = raw.get("reporting")
    permissions = raw.get("permissions")
    if not all(
        isinstance(section, dict)
        for section in (
            assay,
            environment,
            sequencing,
            files,
            analysis,
            authentication,
            genelist,
            reporting,
            permissions,
        )
    ):
        raise RuntimeError(
            "clinical vocabulary requires assay, environment, sequencing, files, analysis, "
            "authentication, genelist, reporting, and permissions tables"
        )

    assay_categories = _identifier_tuple(assay.get("categories"), key="assay.categories")
    assay_families = _identifier_tuple(assay.get("families"), key="assay.families")
    base_subpanel_id = _identifier_value(
        assay.get("base_subpanel_id"), key="assay.base_subpanel_id"
    )
    raw_family_categories = assay.get("family_categories")
    raw_family_scopes = assay.get("family_scopes")
    if not isinstance(raw_family_categories, dict) or not isinstance(raw_family_scopes, dict):
        raise RuntimeError("assay requires family_categories and family_scopes tables")
    if set(raw_family_categories) != set(assay_families):
        raise RuntimeError(
            "assay.family_categories must define exactly the configured assay families"
        )
    if set(raw_family_scopes) != set(assay_families):
        raise RuntimeError("assay.family_scopes must define exactly the configured assay families")
    assay_family_categories = {
        family: _identifier_value(
            raw_family_categories[family], key=f"assay.family_categories.{family}"
        )
        for family in assay_families
    }
    invalid_categories = set(assay_family_categories.values()) - set(assay_categories)
    if invalid_categories:
        raise RuntimeError(
            "assay.family_categories contains unknown assay category values: "
            + ", ".join(sorted(invalid_categories))
        )
    assay_family_scopes = {
        family: _identifier_value(raw_family_scopes[family], key=f"assay.family_scopes.{family}")
        for family in assay_families
    }

    environment_options = _identifier_tuple(environment.get("options"), key="environment.options")
    default_environment = _identifier_value(environment.get("default"), key="environment.default")
    if default_environment not in environment_options:
        raise RuntimeError("environment.default must be one of environment.options")

    platforms = _string_tuple(sequencing.get("platforms"), key="sequencing.platforms")
    read_modes = _string_tuple(
        sequencing.get("read_modes"), key="sequencing.read_modes", uppercase=True
    )

    sample_file_keys: dict[str, tuple[str, ...]] = {}
    for category in assay_categories:
        file_section = files.get(category)
        if not isinstance(file_section, dict):
            raise RuntimeError(f"clinical vocabulary requires files.{category} table")
        sample_file_keys[category] = _identifier_tuple(
            file_section.get("keys"), key=f"files.{category}.keys"
        )

    raw_required = files.get("required_by_family")
    if not isinstance(raw_required, dict):
        raise RuntimeError("clinical vocabulary requires files.required_by_family table")
    required_file_keys_by_family: dict[str, tuple[str, ...]] = {}
    for family, category in assay_family_categories.items():
        required = _identifier_tuple(
            raw_required.get(family), key=f"files.required_by_family.{family}"
        )
        invalid = set(required) - set(sample_file_keys[category])
        if invalid:
            raise RuntimeError(
                f"files.required_by_family.{family} contains invalid {category} file keys: "
                f"{', '.join(sorted(invalid))}"
            )
        required_file_keys_by_family[family] = required

    analysis_file_keys_by_omics: dict[str, dict[str, tuple[str, ...]]] = {}
    for category in assay_categories:
        analysis_section = analysis.get(category)
        if not isinstance(analysis_section, dict):
            raise RuntimeError(f"clinical vocabulary requires analysis.{category} table")
        analysis_types = _string_tuple(
            analysis_section.get("types"), key=f"analysis.{category}.types", uppercase=True
        )
        raw_bindings = analysis_section.get("file_keys")
        if not isinstance(raw_bindings, dict):
            raise RuntimeError(f"clinical vocabulary requires analysis.{category}.file_keys table")
        if set(raw_bindings) != set(analysis_types):
            raise RuntimeError(
                f"analysis.{category}.file_keys must define exactly the enabled analysis types"
            )
        bindings: dict[str, tuple[str, ...]] = {}
        for analysis_type in analysis_types:
            binding = _identifier_tuple(
                raw_bindings.get(analysis_type),
                key=f"analysis.{category}.file_keys.{analysis_type}",
            )
            invalid = set(binding) - set(sample_file_keys[category])
            if invalid:
                raise RuntimeError(
                    f"analysis.{category}.file_keys.{analysis_type} contains invalid "
                    f"{category} file keys: {', '.join(sorted(invalid))}"
                )
            bindings[analysis_type] = binding
        analysis_file_keys_by_omics[category] = bindings

    auth_type_options = _identifier_tuple(
        authentication.get("providers"), key="authentication.providers"
    )
    unsupported_providers = set(auth_type_options) - _SOFTWARE_AUTH_PROVIDERS
    if unsupported_providers:
        raise RuntimeError(
            "authentication.providers contains unsupported provider(s): "
            + ", ".join(sorted(unsupported_providers))
        )

    genelist_standard_types = _identifier_tuple(
        genelist.get("standard_types"), key="genelist.standard_types"
    )
    genelist_adhoc_types = _identifier_tuple(
        genelist.get("adhoc_types"), key="genelist.adhoc_types"
    )
    overlap = set(genelist_standard_types) & set(genelist_adhoc_types)
    if overlap:
        raise RuntimeError(
            "genelist standard_types and adhoc_types must not overlap: "
            + ", ".join(sorted(overlap))
        )
    required_aspc_reporting_fields = _identifier_tuple(
        reporting.get("required_aspc_fields"), key="reporting.required_aspc_fields"
    )
    permission_categories = _string_tuple(
        permissions.get("categories"), key="permissions.categories", lowercase=False
    )

    return ClinicalVocabulary(
        assay_categories=assay_categories,
        assay_families=assay_families,
        assay_family_categories=assay_family_categories,
        assay_family_scopes=assay_family_scopes,
        base_subpanel_id=base_subpanel_id,
        environment_options=environment_options,
        default_environment=default_environment,
        platforms=platforms,
        read_modes=read_modes,
        sample_file_keys=sample_file_keys,
        required_file_keys_by_family=required_file_keys_by_family,
        analysis_file_keys_by_omics=analysis_file_keys_by_omics,
        auth_type_options=auth_type_options,
        genelist_standard_types=genelist_standard_types,
        genelist_adhoc_types=genelist_adhoc_types,
        required_aspc_reporting_fields=required_aspc_reporting_fields,
        permission_categories=permission_categories,
    )


CLINICAL_VOCABULARY = load_clinical_vocabulary()
