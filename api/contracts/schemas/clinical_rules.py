"""Strict contracts for repository-owned clinical reporting rules."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.config.constants import normalize_clinical_identifier


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
    when: list[ClinicalRuleCondition] = Field(default_factory=list)
    template: str
    heading: bool = True
    stop: bool = True

    @field_validator("rule_id", "section")
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


class ClinicalRuleAnalysisBlock(BaseModel):
    """One ASPC analysis type's explicit reporting decision and rules."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    rules: list[ClinicalReportingRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_rules(self) -> "ClinicalRuleAnalysisBlock":
        if not self.enabled and self.rules:
            raise ValueError("disabled analysis blocks cannot contain executable rules")
        return self


class ClinicalRuleSetMetadata(BaseModel):
    """Stable static scope for one ASP and optional subpanel."""

    model_config = ConfigDict(extra="forbid")

    analyte: Literal["dna", "rna"]
    asp_id: str
    subpanel_id: str = "base"

    @field_validator("asp_id", "subpanel_id", mode="before")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        return normalize_clinical_identifier(value, label="rule-set identity")

    @property
    def rule_set_id(self) -> str:
        """Return the deterministic source identity used in report provenance."""
        return f"{self.asp_id}__{self.subpanel_id}"


class ClinicalRuleSetSource(BaseModel):
    """Repository-authored clinical rule bundle.

    ``base.yaml`` is the complete no-subpanel rule set and the runtime fallback
    when a matching subpanel file is intentionally absent.
    """

    model_config = ConfigDict(extra="forbid")

    rule_set: ClinicalRuleSetMetadata
    document_rules: list[ClinicalReportingRule] = Field(default_factory=list)
    analyses: dict[str, ClinicalRuleAnalysisBlock] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_rules(self) -> "ClinicalRuleSetSource":
        all_rules = list(self.document_rules)
        for analysis in self.analyses.values():
            all_rules.extend(analysis.rules)
        if not all_rules:
            raise ValueError("a clinical rule set must contain at least one executable rule")
        rule_ids = [rule.rule_id for rule in all_rules]
        duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate rule_id values: {duplicates}")
        priorities = [(rule.family, rule.priority) for rule in all_rules]
        duplicates = sorted(
            {
                f"{family}:{priority}"
                for family, priority in priorities
                if priorities.count((family, priority)) > 1
            }
        )
        if duplicates:
            raise ValueError(
                "priorities must be unique within each rule family: " + ", ".join(duplicates)
            )
        return self

    def executable_rules(self, reporting_analyses: set[str]) -> list[ClinicalReportingRule]:
        """Return document rules plus enabled blocks allowed by the ASPC."""
        rules = list(self.document_rules)
        for analysis_name, block in self.analyses.items():
            if analysis_name in reporting_analyses and block.enabled:
                rules.extend(block.rules)
        return rules


class ClinicalRuleSourceRef(BaseModel):
    """Static rule source recorded with a persisted report."""

    model_config = ConfigDict(extra="forbid")

    rule_set_id: str
    source_path: str
    content_hash: str


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

    source: ClinicalRuleSourceRef
    sections: dict[str, list[str]] = Field(default_factory=dict)
    section_headings: dict[str, bool] = Field(default_factory=dict)
    trace: list[ClinicalRuleTraceEntry] = Field(default_factory=list)
