"""Contracts for authored and published clinical reporting rules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.contracts.schemas.base import _StrictDocBase


class ClinicalRuleFamily(str, Enum):
    """Supported evaluation phases."""

    FINDING_TEXT = "finding_text"
    RESULT_TEXT = "result_text"
    SUMMARY_TEXT = "summary_text"


class ClinicalRuleOperator(str, Enum):
    """Allowlisted condition operators."""

    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"
    EXISTS = "exists"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class ClinicalRuleScope(BaseModel):
    """Deployment scope for a rule set."""

    model_config = ConfigDict(extra="forbid")

    analyte: Literal["dna", "rna"]
    assay_ids: list[str] = Field(default_factory=list)
    assay_groups: list[str] = Field(default_factory=list)
    subpanel_ids: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)

    @field_validator("assay_ids", "assay_groups", "subpanel_ids", "environments", mode="before")
    @classmethod
    def _normalize_values(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else ([value] if value else [])
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class ClinicalRuleCondition(BaseModel):
    """One typed predicate evaluated against prepared report facts."""

    model_config = ConfigDict(extra="forbid")

    fact: str
    operator: ClinicalRuleOperator = ClinicalRuleOperator.EQ
    value: Any = None

    @field_validator("fact")
    @classmethod
    def _validate_fact(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("fact cannot be empty")
        return value

    @model_validator(mode="after")
    def _validate_value(self) -> "ClinicalRuleCondition":
        if self.operator != ClinicalRuleOperator.EXISTS and self.value is None:
            raise ValueError(f"operator '{self.operator}' requires a value")
        if self.operator in {
            ClinicalRuleOperator.IN,
            ClinicalRuleOperator.NOT_IN,
            ClinicalRuleOperator.OVERLAPS,
        } and not isinstance(self.value, list):
            raise ValueError(f"operator '{self.operator}' requires a list value")
        if self.operator == ClinicalRuleOperator.EXISTS and not isinstance(self.value, bool):
            raise ValueError("operator 'exists' requires a boolean value")
        return self


class ClinicalReportingRule(BaseModel):
    """One ordered clinical text rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    family: ClinicalRuleFamily
    section: str
    priority: int = Field(ge=1, le=100_000)
    description: str
    when: list[ClinicalRuleCondition] = Field(default_factory=list)
    template: str
    stop: bool = True

    @field_validator("rule_id", "section", "description", "template")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rule text fields cannot be empty")
        return value


class ClinicalRuleSetMetadata(BaseModel):
    """Authored rule-set identity and lifecycle."""

    model_config = ConfigDict(extra="forbid")

    rule_set_id: str
    version: str
    title: str
    status: Literal["draft", "active", "retired"] = "draft"
    language: str = "sv"
    scope: ClinicalRuleScope
    required_facts: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("rule_set_id", "version", "title", "language")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rule-set identity fields cannot be empty")
        return value

    @field_validator("required_facts", mode="before")
    @classmethod
    def _normalize_required_facts(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else ([value] if value else [])
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class ClinicalRuleSetSource(BaseModel):
    """Repository-authored clinical rule bundle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    rule_set: ClinicalRuleSetMetadata
    rules: list[ClinicalReportingRule]

    @model_validator(mode="after")
    def _validate_rules(self) -> "ClinicalRuleSetSource":
        if not self.rules:
            raise ValueError("a clinical rule set must contain at least one rule")
        rule_ids = [rule.rule_id for rule in self.rules]
        duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate rule_id values: {duplicates}")
        priorities = [(rule.family, rule.priority) for rule in self.rules]
        duplicate_priorities = sorted(
            {
                f"{family}:{priority}"
                for family, priority in priorities
                if priorities.count((family, priority)) > 1
            }
        )
        if duplicate_priorities:
            raise ValueError(
                f"priorities must be unique within each rule family: {duplicate_priorities}"
            )
        return self


class ClinicalRuleReleaseDoc(_StrictDocBase):
    """Immutable compiled rule release stored for runtime and audit use."""

    rule_set_id: str
    version: str
    status: Literal["active", "retired"]
    schema_version: int = 1
    content_hash: str
    source_path: str
    source: ClinicalRuleSetSource
    published_by: str
    published_on: datetime


class ClinicalRuleReleaseRef(BaseModel):
    """Reference embedded in an ASPC reporting configuration."""

    model_config = ConfigDict(extra="forbid")

    release_id: Any
    rule_set_id: str
    version: str
    content_hash: str


class ClinicalRuleReleaseBindRequest(BaseModel):
    """Request to bind a published release by rotating an active ASPC."""

    model_config = ConfigDict(extra="forbid")

    release_id: str

    @field_validator("release_id")
    @classmethod
    def _validate_release_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("release_id cannot be empty")
        return value


class ClinicalRuleTraceEntry(BaseModel):
    """One auditable rule evaluation decision."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    family: ClinicalRuleFamily
    section: str
    matched: bool
    finding_index: int | None = None
    missing_facts: list[str] = Field(default_factory=list)
    rendered_text: str | None = None


class ClinicalRuleEvaluation(BaseModel):
    """Rendered report text and deterministic evaluation trace."""

    model_config = ConfigDict(extra="forbid")

    release: ClinicalRuleReleaseRef
    sections: dict[str, list[str]] = Field(default_factory=dict)
    trace: list[ClinicalRuleTraceEntry] = Field(default_factory=list)
