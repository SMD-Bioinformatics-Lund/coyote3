"""Reusable configuration profile authoring and publication contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase


class ConfigurationScope(_StrictDocBase):
    """Select a supported biological, technical and optional environment binding."""

    asp_group: str | None = None
    diagnosis_id: str | None = None
    asp_id: str | None = None
    asp_category: Literal["dna", "rna"] | None = None
    asp_family: str | None = None
    environment: str | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        """Reject incomplete family bindings and scopes outside the registered vocabulary."""
        if (self.diagnosis_id or self.asp_id or self.asp_family) and not self.asp_group:
            raise ValueError("Diagnosis, assay and family bindings require a group")
        if bool(self.asp_family) != bool(self.asp_category):
            raise ValueError("Family and modality must be selected together")
        if self.asp_id and self.asp_family:
            raise ValueError("Use an assay binding or a family binding, not both")
        if (
            self.asp_family
            and CLINICAL_VOCABULARY.assay_family_categories.get(self.asp_family)
            != self.asp_category
        ):
            raise ValueError("Family does not belong to the selected modality")
        if self.environment and self.environment not in CLINICAL_VOCABULARY.environment_options:
            raise ValueError("Unknown sample environment")
        if self.diagnosis_id == "base":
            raise ValueError("Base uses the binding without a named diagnosis")
        return self

    def rank(self) -> tuple[int, int]:
        """Return broad-to-specific precedence, then shared-before-environment order."""
        rank = (
            (7 if self.diagnosis_id else 6)
            if self.asp_id
            else (
                (5 if self.asp_family else 4)
                if self.diagnosis_id
                else (3 if self.asp_family else 2 if self.asp_group else 1)
            )
        )
        return rank, int(self.environment is not None)

    def matches(self, configuration: dict, panel: dict) -> bool:
        """Match only explicitly selected dimensions against a configuration's registered assay."""
        context = {
            "asp_group": panel["asp_group"],
            "asp_id": panel["asp_id"],
            "asp_category": panel["asp_category"],
            "asp_family": panel["asp_family"],
            "diagnosis_id": configuration["diagnosis_id"],
            "environment": configuration["environment"],
        }
        return all(
            value is None or context[key] == value for key, value in self.model_dump().items()
        )


class ConfigurationProfileDraft(_StrictDocBase):
    """Immutable proposed profile content and its explicit reusable scope bindings."""

    profile_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["filters", "reporting", "clinical_rules", "template"]
    bindings: list[ConfigurationScope] = Field(min_length=1, max_length=100)
    content: dict[str, Any]
    reason: str = Field(min_length=3, max_length=2000)


class ConfigurationProfileDoc(ConfigurationProfileDraft, _StrictCollectionDocBase):
    """A retained profile revision, independently published before configuration compilation."""

    version: int = Field(ge=1)
    status: Literal["draft", "published"] = "draft"
    is_current: bool = False
    content_hash: str
    created_by: str
    created_on: datetime
    published_by: str | None = None
    published_on: datetime | None = None


class ProfilePublication(_StrictDocBase):
    """Require the reviewer to identify the exact content reviewed."""

    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=3, max_length=2000)


class ConfigurationPromotionRequest(_StrictDocBase):
    """Propose explicit reuse of an exact configuration release in another environment."""

    source_id: str = Field(pattern=r"^[a-fA-F0-9]{24}$")
    target_environment: str
    evidence: list[str] = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def validate_target(self):
        """Require a registered environment and nonblank validation evidence references."""
        if self.target_environment not in CLINICAL_VOCABULARY.environment_options:
            raise ValueError("Choose a registered target environment")
        if any(not item.strip() or len(item) > 2000 for item in self.evidence):
            raise ValueError("Validation evidence must contain nonblank references")
        return self


class ConfigurationPromotionDoc(_StrictCollectionDocBase):
    """Retain the reviewed candidate, exact source, evidence and publication result."""

    source_id: str
    source_hash: str
    candidate: dict[str, Any]
    content_hash: str
    expected_target_version: int
    evidence: list[str]
    reason: str
    created_by: str
    created_on: datetime
    status: Literal["pending", "approved"] = "pending"
    approved_by: str | None = None
    approved_on: datetime | None = None
    target_id: str | None = None
