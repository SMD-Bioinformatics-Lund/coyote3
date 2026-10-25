"""Validate center-owned global and caller-specific filter presentation metadata."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY, ClinicalVocabulary
from coyote3.config.paths import PACKAGE_CONFIG_DIR
from coyote3.config.selection import center_policy_path


class FilterFlagDescription(BaseModel):
    """Display text and severity for a pipeline flag, independent of admission policy."""

    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    severity: Literal["pass", "warn", "fail", "info", "neutral"] | None = None
    description: str | None = None
    hidden: bool = False


class FilterFlagGroups(BaseModel):
    """Ordered global or caller-specific flag matching groups."""

    model_config = ConfigDict(extra="forbid")
    exact: dict[str, FilterFlagDescription] = Field(default_factory=dict)
    prefixes: dict[str, FilterFlagDescription] = Field(default_factory=dict)
    terms: dict[str, FilterFlagDescription] = Field(default_factory=dict)

    @field_validator("exact", "prefixes", "terms", mode="before")
    @classmethod
    def normalize_keys(cls, value: object) -> object:
        """Normalize flag keys without permitting case-insensitive collisions.

        Args:
            value: Mapping from pipeline flag names to display metadata.

        Returns:
            Mapping with uppercase keys, preserving prefix order.

        Raises:
            ValueError: A flag name is blank or duplicates another normalized name.
        """
        if not isinstance(value, dict):
            return value
        normalized = {str(key).strip().upper(): item for key, item in value.items()}
        if "" in normalized or len(normalized) != len(value):
            raise ValueError("Flag keys must be nonempty and unique ignoring case")
        return normalized


class FilterFlagConfiguration(FilterFlagGroups):
    """Flag metadata partitioned by analysis and configured caller identity."""

    callers: dict[str, dict[str, FilterFlagGroups]] = Field(default_factory=dict)


def load_filter_flag_metadata(
    path: str | Path | None = None,
    vocabulary: ClinicalVocabulary = CLINICAL_VOCABULARY,
) -> dict:
    """Read and validate global flags and caller-scoped overrides.

    Args:
        path: Explicit YAML file. None uses the selected profile or software defaults.
        vocabulary: Caller registries used to reject unknown analysis/caller keys.

    Returns:
        JSON-compatible display metadata and the corresponding caller options.

    Raises:
        OSError: The file cannot be read.
        yaml.YAMLError: YAML syntax is invalid.
        ValueError: Metadata is malformed or references an unconfigured caller.
    """
    path = (
        path
        if path is not None
        else center_policy_path(
            "filter_flag_metadata.yaml", PACKAGE_CONFIG_DIR / "filter_flag_defaults.yaml"
        )
    )
    with Path(path).open(encoding="utf-8") as handle:
        config = FilterFlagConfiguration.model_validate(yaml.safe_load(handle) or {})
    options = vocabulary.caller_options()
    for analysis, callers in config.callers.items():
        if analysis not in options:
            raise ValueError(f"Unknown filter metadata analysis: {analysis}")
        if set(callers) - set(options[analysis]):
            raise ValueError(f"Filter metadata references unconfigured {analysis} callers")
    return {**config.model_dump(exclude_none=True), "caller_options": options}


def filter_flag_options(analysis: str) -> list[str]:
    """Return configured literal FILTER names for one analysis.

    Args:
        analysis: Registered analysis key, such as snv.

    Returns:
        Sorted global and caller-specific exact and term names. Hidden badges
        remain selectable. Prefix styling rules are not literal flag values.

    Raises:
        OSError: The configured metadata file cannot be read.
        ValueError: The configured flag metadata is invalid.
    """
    metadata = load_filter_flag_metadata()
    groups = [metadata, *metadata.get("callers", {}).get(analysis, {}).values()]
    return sorted({key for group in groups for kind in ("exact", "terms") for key in group[kind]})
