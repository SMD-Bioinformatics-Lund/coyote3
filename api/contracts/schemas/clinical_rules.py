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
    """Exact assay/subpanel identity for a clinical rule set."""

    model_config = ConfigDict(extra="forbid")

    analyte: Literal["dna", "rna"]
    assay_id: str
    subpanel_id: str = "base"

    @field_validator("assay_id", "subpanel_id", mode="before")
    @classmethod
    def _normalize_identifier(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("clinical rule assay and subpanel identifiers cannot be empty")
        return normalized


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
    source_locator: str
    when: list[ClinicalRuleCondition] = Field(default_factory=list)
    template: str
    heading: bool = True
    stop: bool = True

    @field_validator("rule_id", "section", "description", "source_locator")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rule text fields cannot be empty")
        return value

    @field_validator("template")
    @classmethod
    def _validate_template(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule template cannot be empty")
        return value


class DeferredClinicalReportingRule(BaseModel):
    """Verbatim source rule blocked until its fact contract exists."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    description: str
    source_locator: str
    template: str
    required_fact_contract: list[str]
    activation_note: str

    @field_validator(
        "rule_id",
        "description",
        "source_locator",
        "activation_note",
    )
    @classmethod
    def _validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("deferred clinical rule text fields cannot be empty")
        return value

    @field_validator("template")
    @classmethod
    def _validate_template(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("deferred clinical rule template cannot be empty")
        return value

    @field_validator("required_fact_contract", mode="before")
    @classmethod
    def _normalize_fact_contract(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else ([value] if value else [])
        normalized = list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
        if not normalized:
            raise ValueError("deferred clinical rules require a fact contract")
        return normalized


class ClinicalRuleSourceProvenance(BaseModel):
    """Immutable identity of the authority from which wording was transcribed."""

    model_config = ConfigDict(extra="forbid")

    authority: Literal["coyote_master", "old_coyote", "clinical_workbook"]
    reference: str
    revision: str
    content_sha256: str
    text_policy: Literal["verbatim"] = "verbatim"

    @field_validator("reference", "revision")
    @classmethod
    def _validate_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("clinical rule source references cannot be empty")
        return value

    @field_validator("content_sha256")
    @classmethod
    def _validate_checksum(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        return value


class ClinicalRuleValidation(BaseModel):
    """Governance evidence required before a rule set can be published."""

    model_config = ConfigDict(extra="forbid")

    approval_status: Literal["pending", "inherited", "approved"] = "pending"
    approval_reference: str | None = None
    golden_case_ids: list[str] = Field(default_factory=list)

    @field_validator("approval_reference")
    @classmethod
    def _normalize_approval_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("golden_case_ids", mode="before")
    @classmethod
    def _normalize_golden_cases(cls, value: Any) -> list[str]:
        values = value if isinstance(value, list) else ([value] if value else [])
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class ClinicalRuleSetMetadata(BaseModel):
    """Authored rule-set identity and lifecycle."""

    model_config = ConfigDict(extra="forbid")

    rule_set_id: str
    version: str
    title: str
    status: Literal["draft", "active", "retired"] = "draft"
    language: str = "sv"
    scope: ClinicalRuleScope
    provenance: ClinicalRuleSourceProvenance
    validation: ClinicalRuleValidation = Field(default_factory=ClinicalRuleValidation)
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

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> "ClinicalRuleSetMetadata":
        expected = f"{self.scope.assay_id}__{self.scope.subpanel_id}"
        if self.rule_set_id != expected:
            raise ValueError(
                f"rule_set_id must identify the exact assay/subpanel scope: expected '{expected}'"
            )
        return self

    @model_validator(mode="after")
    def _validate_activation_evidence(self) -> "ClinicalRuleSetMetadata":
        if self.status != "active":
            return self
        if self.validation.approval_status not in {"inherited", "approved"}:
            raise ValueError("active clinical rule sets require inherited or explicit approval")
        if not self.validation.approval_reference:
            raise ValueError("active clinical rule sets require an approval_reference")
        if not self.validation.golden_case_ids:
            raise ValueError("active clinical rule sets require at least one golden_case_id")
        return self


class ClinicalRuleSetSource(BaseModel):
    """Repository-authored clinical rule bundle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[3] = 3
    rule_set: ClinicalRuleSetMetadata
    rules: list[ClinicalReportingRule]
    deferred_rules: list[DeferredClinicalReportingRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_rules(self) -> "ClinicalRuleSetSource":
        if not self.rules:
            raise ValueError("a clinical rule set must contain at least one rule")
        rule_ids = [rule.rule_id for rule in self.rules]
        duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate rule_id values: {duplicates}")
        deferred_ids = [rule.rule_id for rule in self.deferred_rules]
        deferred_duplicates = sorted(
            {rule_id for rule_id in deferred_ids if deferred_ids.count(rule_id) > 1}
        )
        if deferred_duplicates:
            raise ValueError(f"duplicate deferred rule_id values: {deferred_duplicates}")
        overlap = sorted(set(rule_ids) & set(deferred_ids))
        if overlap:
            raise ValueError(f"rule_id cannot be both executable and deferred: {overlap}")
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
    schema_version: int = 3
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
    section_headings: dict[str, bool] = Field(default_factory=dict)
    trace: list[ClinicalRuleTraceEntry] = Field(default_factory=list)
