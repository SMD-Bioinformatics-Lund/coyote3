"""Canonical contracts for governed clinical reporting rule sets."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.config.constants import normalize_clinical_identifier
from api.contracts.schemas.base import _StrictCollectionDocBase


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ClinicalRuleStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_CLINICAL_REVIEW = "in_clinical_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    RETIRED = "retired"


class ClinicalRuleOperator(str, Enum):
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
    BETWEEN = "between"
    IS_EMPTY = "is_empty"
    IS_UNKNOWN = "is_unknown"


class ClinicalRulePredicate(_StrictModel):
    type: Literal["predicate"] = "predicate"
    fact: str
    operator: ClinicalRuleOperator = ClinicalRuleOperator.EQ
    value: Any = None

    @field_validator("fact")
    @classmethod
    def _fact_is_present(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("fact cannot be empty")
        return value

    @model_validator(mode="after")
    def _operator_value_contract(self) -> "ClinicalRulePredicate":
        no_value = {ClinicalRuleOperator.IS_EMPTY, ClinicalRuleOperator.IS_UNKNOWN}
        if self.operator not in no_value and self.value is None:
            raise ValueError(f"operator '{self.operator}' requires a value")
        if self.operator == ClinicalRuleOperator.EXISTS and not isinstance(self.value, bool):
            raise ValueError("operator 'exists' requires a boolean value")
        if self.operator in {
            ClinicalRuleOperator.IN,
            ClinicalRuleOperator.NOT_IN,
            ClinicalRuleOperator.OVERLAPS,
            ClinicalRuleOperator.BETWEEN,
        } and not isinstance(self.value, list):
            raise ValueError(f"operator '{self.operator}' requires a list value")
        if self.operator == ClinicalRuleOperator.BETWEEN and len(self.value) != 2:
            raise ValueError("operator 'between' requires exactly two values")
        return self


class ClinicalRuleAll(_StrictModel):
    type: Literal["all"] = "all"
    children: list["ClinicalCondition"] = Field(min_length=1)


class ClinicalRuleAny(_StrictModel):
    type: Literal["any"] = "any"
    children: list["ClinicalCondition"] = Field(min_length=1)


class ClinicalRuleNot(_StrictModel):
    type: Literal["not"] = "not"
    child: "ClinicalCondition"


class ClinicalRuleCountComparison(_StrictModel):
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte"]
    value: int = Field(ge=0)


class ClinicalRuleCollectionMatch(_StrictModel):
    type: Literal["collection_match"] = "collection_match"
    collection: Literal["findings", "biomarkers", "applied_gene_lists", "tier_summaries"]
    quantifier: Literal["any", "none", "all", "count"]
    where: "ClinicalCondition"
    count: ClinicalRuleCountComparison | None = None

    @model_validator(mode="after")
    def _count_contract(self) -> "ClinicalRuleCollectionMatch":
        if (self.quantifier == "count") != (self.count is not None):
            raise ValueError("count comparison is required only for the count quantifier")
        return self


ClinicalCondition = Annotated[
    ClinicalRulePredicate
    | ClinicalRuleAll
    | ClinicalRuleAny
    | ClinicalRuleNot
    | ClinicalRuleCollectionMatch,
    Field(discriminator="type"),
]


class ClinicalTextOutput(_StrictModel):
    type: Literal["text"] = "text"
    value: str = Field(min_length=1)


class ClinicalFactOutput(_StrictModel):
    type: Literal["fact"] = "fact"
    path: str
    formatter: Literal["text", "gene_symbol", "upper", "lower"] = "text"
    missing: Literal["error", "omit"] = "error"


class ClinicalListOutput(_StrictModel):
    type: Literal["list"] = "list"
    path: str
    conjunction: str = "and"
    formatter: Literal["text", "gene_symbol", "upper", "lower"] = "text"
    missing: Literal["error", "omit"] = "error"


class ClinicalNumberOutput(_StrictModel):
    type: Literal["number"] = "number"
    path: str
    precision: int = Field(default=0, ge=0, le=6)
    unit: Literal["", "%", "x"] = ""
    missing: Literal["error", "omit"] = "error"


class ClinicalMessageOutput(_StrictModel):
    type: Literal["message"] = "message"
    count_path: str
    one: str
    other: str


class ClinicalRendererOutput(_StrictModel):
    type: Literal["renderer"] = "renderer"
    name: Literal["dna_report_intro", "tier_summary", "fusion_summary"]
    source: str | None = None


class ClinicalParagraphBreakOutput(_StrictModel):
    type: Literal["paragraph_break"] = "paragraph_break"


ClinicalOutputNode = Annotated[
    ClinicalTextOutput
    | ClinicalFactOutput
    | ClinicalListOutput
    | ClinicalNumberOutput
    | ClinicalMessageOutput
    | ClinicalRendererOutput
    | ClinicalParagraphBreakOutput,
    Field(discriminator="type"),
]


class ClinicalRule(_StrictModel):
    rule_id: str
    name: str
    order: int = Field(ge=0)
    enabled: bool = True
    condition: ClinicalCondition | None = None
    output: list[ClinicalOutputNode] = Field(min_length=1)
    references: list[str] = Field(default_factory=list)
    rationale: str | None = None

    @field_validator("rule_id", "name")
    @classmethod
    def _nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rule identity and name cannot be empty")
        return value


class ClinicalRuleEvaluationScope(_StrictModel):
    mode: Literal["once", "each_finding", "each_item"] = "once"
    collection: Literal["findings", "biomarkers", "applied_gene_lists", "tier_summaries"] | None = (
        None
    )

    @model_validator(mode="after")
    def _collection_contract(self) -> "ClinicalRuleEvaluationScope":
        if (self.mode == "each_item") != (self.collection is not None):
            raise ValueError("collection is required only for each_item evaluation")
        return self


class ClinicalRuleBlock(_StrictModel):
    block_id: str
    name: str
    analysis: str | None = None
    evaluation: ClinicalRuleEvaluationScope = Field(default_factory=ClinicalRuleEvaluationScope)
    section: str
    section_order: int = Field(ge=0)
    block_order: int = Field(ge=0)
    show_heading: bool = True
    match_strategy: Literal["all_matches", "first_match", "exactly_one", "at_most_one"]
    rules: list[ClinicalRule] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_rules(self) -> "ClinicalRuleBlock":
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError(f"block '{self.block_id}' contains duplicate rule IDs")
        orders = [rule.order for rule in self.rules]
        if len(orders) != len(set(orders)):
            raise ValueError(f"block '{self.block_id}' contains duplicate rule ordering")
        return self


class ClinicalRuleScope(_StrictModel):
    asp_id: str
    subpanel_id: str
    analyte: Literal["dna", "rna"]
    language: str = Field(default="sv", min_length=2, max_length=16)

    @field_validator("asp_id", "subpanel_id", mode="before")
    @classmethod
    def _normalize_identity(cls, value: Any) -> str:
        return normalize_clinical_identifier(value, label="clinical rule scope")

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return value.strip().lower()


class ClinicalAnalysisDeclaration(_StrictModel):
    narrative: Literal["enabled", "none"]


class ClinicalRuleReview(_StrictModel):
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    clinical_reviewer: str | None = None
    publisher: str | None = None
    clinical_decision_at: datetime | None = None
    clinical_decision_reason: str | None = None


class ClinicalRuleLifecycleEvent(_StrictModel):
    action: str
    actor: str
    occurred_at: datetime
    reason: str | None = None


class ClinicalRuleProvenance(_StrictModel):
    """Origin retained when a draft is copied or imported."""

    source: Literal["ui", "template", "api", "import"]
    source_rule_set_id: str | None = None
    source_content_version: int | None = Field(default=None, ge=1)
    source_revision: int | None = Field(default=None, ge=1)
    imported_schema_version: int | None = Field(default=None, ge=1)


class ClinicalRuleTestCase(_StrictModel):
    test_id: str
    name: str
    facts: dict[str, Any]
    expected_rule_ids: list[str] = Field(default_factory=list)
    expected_sections: dict[str, list[str]] = Field(default_factory=dict)


class ClinicalRuleSetDoc(_StrictCollectionDocBase):
    """One draft or immutable released version of a clinical rule scope."""

    rule_set_id: str
    schema_version: Literal[1] = 1
    content_version: int = Field(ge=1)
    revision: int = Field(ge=1)
    scope: ClinicalRuleScope
    name: str = Field(min_length=1, max_length=160)
    status: ClinicalRuleStatus
    active: bool = False
    minimum_engine_version: int = Field(default=1, ge=1)
    analysis_declarations: dict[str, ClinicalAnalysisDeclaration] = Field(default_factory=dict)
    terminology: dict[str, Any] = Field(default_factory=dict)
    blocks: list[ClinicalRuleBlock] = Field(default_factory=list)
    test_cases: list[ClinicalRuleTestCase] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    provenance: ClinicalRuleProvenance | None = None
    change_summary: str = ""
    review: ClinicalRuleReview = Field(default_factory=ClinicalRuleReview)
    lifecycle: list[ClinicalRuleLifecycleEvent] = Field(default_factory=list)
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str
    published_at: datetime | None = None
    published_by: str | None = None
    effective_from: datetime | None = None
    retired_at: datetime | None = None
    retired_by: str | None = None
    content_hash: str | None = None

    @model_validator(mode="after")
    def _document_invariants(self) -> "ClinicalRuleSetDoc":
        expected_id = f"{self.scope.asp_id}__{self.scope.subpanel_id}__{self.scope.language}"
        if self.rule_set_id != expected_id:
            raise ValueError(f"rule_set_id must be '{expected_id}'")
        block_ids = [block.block_id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("block IDs must be unique")
        rule_ids = [rule.rule_id for block in self.blocks for rule in block.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule IDs must be unique across the rule set")
        if self.status == ClinicalRuleStatus.PUBLISHED:
            if not self.published_at or not self.published_by:
                raise ValueError("published rule sets require publication metadata")
        elif self.active:
            raise ValueError("only a published rule set can be active")
        return self


class ClinicalRuleRevisionDoc(_StrictCollectionDocBase):
    rule_set_oid: str
    rule_set_id: str
    content_version: int = Field(ge=1)
    revision: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    reason: str | None = Field(default=None, max_length=1000)
    previous_revision_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    document: ClinicalRuleSetDoc

    @model_validator(mode="after")
    def _snapshot_identity_matches_document(self) -> "ClinicalRuleRevisionDoc":
        if self.document.id_ is None or self.rule_set_oid != str(self.document.id_):
            raise ValueError("revision rule_set_oid must match document._id")
        if self.rule_set_id != self.document.rule_set_id:
            raise ValueError("revision rule_set_id must match the preserved document")
        if self.content_version != self.document.content_version:
            raise ValueError("revision content_version must match the preserved document")
        if self.revision != self.document.revision:
            raise ValueError("revision number must match the preserved document")
        return self


class ClinicalRuleSourceRef(_StrictModel):
    rule_set_oid: str
    rule_set_id: str
    schema_version: int
    content_version: int
    content_hash: str
    language: str
    effective_from: datetime | None = None


class ClinicalConditionTraceNode(_StrictModel):
    type: str
    label: str
    matched: bool
    missing_facts: list[str] = Field(default_factory=list)
    children: list["ClinicalConditionTraceNode"] = Field(default_factory=list)


class ClinicalRuleTraceEntry(_StrictModel):
    block_id: str
    rule_id: str
    section: str
    matched: bool
    item_identity: str | None = None
    missing_facts: list[str] = Field(default_factory=list)
    rendered_text: str | None = None
    condition_trace: ClinicalConditionTraceNode | None = None


class ClinicalRuleEvaluation(_StrictModel):
    source: ClinicalRuleSourceRef
    sections: dict[str, list[str]] = Field(default_factory=dict)
    section_headings: dict[str, bool] = Field(default_factory=dict)
    trace: list[ClinicalRuleTraceEntry] = Field(default_factory=list)


class ClinicalRuleDraftCreate(_StrictModel):
    source_version_id: str | None = None
    scope: ClinicalRuleScope | None = None
    name: str | None = None
    source: Literal["ui", "template", "api"] = "ui"


class ClinicalRuleImportRequest(_StrictModel):
    """Canonical JSON export uploaded to create a separately governed draft."""

    document: dict[str, Any]
    scope: ClinicalRuleScope
    name: str = Field(min_length=1, max_length=160)


class ClinicalRuleDraftUpdate(_StrictModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    analysis_declarations: dict[str, ClinicalAnalysisDeclaration] | None = None
    terminology: dict[str, Any] | None = None
    blocks: list[ClinicalRuleBlock] | None = None
    test_cases: list[ClinicalRuleTestCase] | None = None
    references: list[dict[str, Any]] | None = None
    change_summary: str | None = None


class ClinicalRuleDecision(_StrictModel):
    reason: str = Field(min_length=1, max_length=1000)
    approve: bool
    publisher: str | None = None


class ClinicalRuleTransition(_StrictModel):
    reason: str = Field(default="", max_length=1000)
    assignee: str | None = Field(default=None, min_length=1, max_length=200)


class ClinicalRulePreviewRequest(_StrictModel):
    facts: dict[str, Any]


class ClinicalRuleValidationResult(_StrictModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ClinicalRuleSetListPayload(_StrictModel):
    items: list[ClinicalRuleSetDoc]
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)
    total: int = Field(ge=0)


class ClinicalRuleSetVersionsPayload(_StrictModel):
    items: list[ClinicalRuleSetDoc]


class ClinicalRuleRevisionsPayload(_StrictModel):
    items: list[ClinicalRuleRevisionDoc]


class ClinicalRuleFactPayload(_StrictModel):
    path: str
    label: str
    group: str
    kind: Literal["boolean", "integer", "number", "string", "string_list", "object_list"]
    operators: list[str]
    scopes: list[str]
    unit: str | None = None
    description: str = ""
    value_options: list[str] = Field(default_factory=list)
    value_format: Literal["gene", "integer", "number", "text"] = "text"


class ClinicalRuleFactsPayload(_StrictModel):
    items: list[ClinicalRuleFactPayload]


class ClinicalRuleAssayOption(_StrictModel):
    asp_id: str
    display_name: str
    analyte: Literal["dna", "rna"]


class ClinicalRuleAuthoringOptionsPayload(_StrictModel):
    assays: list[ClinicalRuleAssayOption]
    condition_values: dict[str, list[str]] = Field(default_factory=dict)
    clinical_reviewers: list[dict[str, str]] = Field(default_factory=list)
    publishers: list[dict[str, str]] = Field(default_factory=list)


class ClinicalRuleTestSample(_StrictModel):
    id: str
    name: str
    asp_id: str | None = None
    subpanel_id: str
    environment: str | None = None
    omics_layer: str | None = None


class ClinicalRuleTestSamplesPayload(_StrictModel):
    items: list[ClinicalRuleTestSample]
    page: int
    per_page: int
    total: int


class ClinicalRuleSamplePreviewPayload(_StrictModel):
    sample: dict[str, Any]
    rule_set: dict[str, Any]
    summary: str
    evaluation: ClinicalRuleEvaluation
    persisted: Literal[False]


ClinicalRuleAll.model_rebuild()
ClinicalRuleAny.model_rebuild()
ClinicalRuleNot.model_rebuild()
ClinicalRuleCollectionMatch.model_rebuild()
ClinicalConditionTraceNode.model_rebuild()
