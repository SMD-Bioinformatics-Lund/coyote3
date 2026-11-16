# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validated per-assay clinical-environment assignments."""

from pydantic import Field, field_validator

from coyote.config.constants import normalize_clinical_identifier, normalize_environment
from coyote.contracts.schemas.base import _StrictDocBase


class AssayAccessGrant(_StrictDocBase):
    """One explicit assay and its permitted configured environments."""

    asp_id: str
    environments: list[str] = Field(default_factory=list)

    @field_validator("asp_id")
    @classmethod
    def normalize_assay(cls, value: str) -> str:
        """Require an explicit canonical assay ID; wildcard accounts require manual review."""
        if not value.strip() or value.strip() == "*":
            raise ValueError("Assay access requires an explicit assay ID")
        return normalize_clinical_identifier(value, label="asp_id")

    @field_validator("environments")
    @classmethod
    def normalize_environments(cls, value: list[str]) -> list[str]:
        """Validate configured environment IDs and reject duplicate selections."""
        normalized = [normalize_environment(item, label="environments") for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Assay access environments must be unique")
        return normalized
