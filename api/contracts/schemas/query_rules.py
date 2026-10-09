"""Contracts for versioned, hierarchical finding-selection policy."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_serializer, model_validator

from api.config.clinical_query_policy import (
    _CNV_EXCEPTION_KEYS,
    _FUSION_EXCEPTION_KEYS,
    _TRANSLOCATION_EXCEPTION_KEYS,
    _exception,
    _finding_exception,
)
from api.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase
from api.domain.query_conditions import compile_condition


class QueryConditionPredicate(_StrictDocBase):
    """Compare a registered finding field with a literal or registered sample-filter reference."""

    type: Literal["predicate"]
    field: str
    operator: str
    value: Any


class QueryConditionGroup(_StrictDocBase):
    """Join a nonempty set of conditions using AND, OR or NOR."""

    type: Literal["all", "any", "nor"]
    children: list["QueryCondition"] = Field(min_length=1, max_length=100)


class QueryConditionNot(_StrictDocBase):
    """Invert one complete condition, including its missing-field behavior."""

    type: Literal["not"]
    child: "QueryCondition"


class QueryConditionElement(_StrictDocBase):
    """Require a condition to match within one element of a registered object array."""

    type: Literal["elem_match"]
    field: str
    condition: "QueryCondition"


QueryCondition = Annotated[
    QueryConditionPredicate | QueryConditionGroup | QueryConditionNot | QueryConditionElement,
    Field(discriminator="type"),
]
CONDITION_ADAPTER = TypeAdapter(QueryCondition)


class QueryConditionTest(_StrictDocBase):
    """Evaluate a condition against caller-supplied examples without database retrieval."""

    analysis: Literal["snv", "cnv", "translocation", "fusion"]
    condition: QueryCondition
    documents: list[dict[str, Any]] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_condition(self):
        """Reject unsupported paths, operators, values and excessive nesting."""
        compile_condition(self.condition.model_dump(), self.analysis)
        return self


class QueryConditionTestResult(_StrictDocBase):
    """Return one match result per input example and the compiled condition predicate."""

    matches: list[bool]
    predicate: dict[str, Any]


class QueryRuleScope(_StrictDocBase):
    """Identify a global, group, assay or subpanel policy for one analysis and intent."""

    assay_group: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$"
    )
    asp_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    subpanel_id: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$"
    )
    analysis: Literal["snv", "cnv", "translocation", "fusion"]
    intent: Literal["somatic", "germline"] = "somatic"

    @model_validator(mode="after")
    def validate_hierarchy(self):
        """Require an assay for subpanel scope and supported analysis intents."""
        if self.subpanel_id == "base":
            self.subpanel_id = None
        if any(
            "__" in value for value in (self.assay_group, self.asp_id, self.subpanel_id) if value
        ):
            raise ValueError("Query scope identifiers cannot contain the reserved __ separator")
        if self.assay_group == "default" or self.asp_id == "all":
            raise ValueError("default group and all assay are reserved query identity tokens")
        if self.subpanel_id and not self.asp_id:
            raise ValueError("A subpanel policy requires its assay")
        if self.asp_id and not self.assay_group:
            raise ValueError("An assay policy requires its group")
        if self.analysis != "snv" and self.intent != "somatic":
            raise ValueError("Only SNV currently supports germline query policies")
        return self

    def key(self) -> str:
        """Return the stable, unambiguous scope identity."""
        datatype = {
            "snv": "snvs",
            "cnv": "cnvs",
            "fusion": "fusions",
            "translocation": "translocations",
        }[self.analysis]
        return "__".join(
            (
                self.assay_group or "default",
                self.asp_id or "all",
                self.subpanel_id or "base",
                f"{self.intent}_{datatype}",
            )
        )


class QueryRuleContent(_StrictDocBase):
    """Inherit, extend or replace exceptions independently of the evidence setting."""

    evidence_mode: Literal["paired", "case_only", "exception_only"] | None = None
    exceptions: list[dict[str, Any]] | None = Field(default=None, max_length=100)
    exception_mode: Literal["replace", "extend"] = "replace"


class QueryRuleDraft(_StrictDocBase):
    """Author a scoped policy without accepting lifecycle or ownership fields."""

    scope: QueryRuleScope
    name: str = ""
    content: QueryRuleContent
    reason: str = Field(min_length=1, max_length=2000, pattern=r"\S")

    @model_validator(mode="after")
    def validate_content(self):
        """Validate typed exceptions and prevent nested scopes or raw queries."""
        self.name = self.scope.key()
        if self.content.evidence_mode is not None and self.scope.analysis != "snv":
            raise ValueError("Evidence mode applies only to SNV")
        identifiers = set()
        for index, item in enumerate(self.content.exceptions or []):
            if "condition" in item:
                item["condition"] = CONDITION_ADAPTER.validate_python(
                    item["condition"]
                ).model_dump()
            for key in ("id", "mode"):
                if not isinstance(item.get(key), str):
                    raise ValueError(f"Exception {key} must be text")
            for key in (
                "genes",
                "consequence_terms",
                "filter_values",
                "chromosomes",
                "simple_ids",
                "info_fields_present",
                "callers",
                "effects",
                "gene_pairs",
                "svtypes",
                "descriptions",
            ):
                if key in item and (
                    not isinstance(item[key], list)
                    or any(not isinstance(value, str) for value in item[key])
                ):
                    raise ValueError(f"Exception {key} must be a list of text values")
            for key in ("position_min", "position_max", "size_min", "size_max"):
                if key in item and (
                    type(item[key]) is not int
                    or item[key] < (1 if key.startswith("position") else 0)
                ):
                    raise ValueError(
                        f"Exception {key} must be an integer within its coordinate range"
                    )
            info = item.get("info_equals", {})
            if not isinstance(info, dict) or any(
                not isinstance(value, (str, int, float, bool)) for value in info.values()
            ):
                raise ValueError("INFO equality values must be scalar literals")
            if set(item) & {"assay_groups", "asp_ids", "subpanel_ids", "intents"}:
                raise ValueError("Exception scope is inherited from the rule-set scope")
            try:
                if self.scope.analysis == "snv":
                    parsed = _exception(item, index=index)
                else:
                    parsed = _finding_exception(
                        item,
                        index=index,
                        analysis=self.scope.analysis,
                        allowed_keys={
                            "cnv": _CNV_EXCEPTION_KEYS,
                            "translocation": _TRANSLOCATION_EXCEPTION_KEYS,
                            "fusion": _FUSION_EXCEPTION_KEYS,
                        }[self.scope.analysis],
                    )
            except RuntimeError as error:
                raise ValueError(str(error)) from error
            if parsed.rule_id in identifiers:
                raise ValueError("Exception identifiers must be unique")
            identifiers.add(parsed.rule_id)
        return self


class QueryRuleUpdate(QueryRuleDraft):
    """Replace a draft only when its inspected revision is still current."""

    expected_revision: int = Field(ge=1)


class QueryRuleTransition(_StrictDocBase):
    """Require an optimistic concurrency token and a clinical change explanation."""

    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class QueryRuleDoc(QueryRuleDraft, _StrictCollectionDocBase):
    """Persist one release version; published content cannot be edited."""

    scope_key: str
    query_id: str = ""
    version: int = Field(ge=1)
    revision: int = Field(default=1, ge=1)
    status: Literal["draft", "approved", "published", "retired"] = "draft"
    created_by: str
    created_on: datetime
    updated_by: str
    updated_on: datetime
    approved_by: str | None = None
    published_by: str | None = None
    published_on: datetime | None = None
    system_installed: bool = False

    @field_serializer("id_", when_used="json")
    def serialize_id(self, value: Any) -> str | None:
        """Render MongoDB identity as a JSON string without changing persistence."""
        return str(value) if value is not None else None

    @model_validator(mode="after")
    def validate_scope_key(self):
        """Reject stored identities that disagree with their clinical scope."""
        if self.scope_key != self.scope.key():
            raise ValueError("Scope key does not match scope")
        if self.query_id and self.query_id != self.scope.key():
            raise ValueError("Query ID does not match scope")
        self.query_id = self.scope.key()
        return self


class QueryRuleList(_StrictDocBase):
    """Return versioned policy records to the authoring workspace."""

    items: list[QueryRuleDoc]


class QueryRuleRevisionDoc(_StrictCollectionDocBase):
    """Preserve a complete query-rule revision and its hash-chain metadata."""

    rule_oid: str
    scope_key: str
    version: int = Field(ge=1)
    revision: int = Field(ge=1)
    action: str
    actor: str
    occurred_at: datetime
    previous_revision_hash: str | None = None
    revision_hash: str
    document: QueryRuleDoc

    @field_serializer("id_", when_used="json")
    def serialize_id(self, value: Any) -> str | None:
        """Serialize the snapshot ObjectId without changing the stored representation."""
        return str(value) if value is not None else None


class QueryRulePreview(_StrictDocBase):
    """Resolve published ancestors with an optional unsaved leaf override."""

    scope: QueryRuleScope
    content: QueryRuleContent | None = None

    @model_validator(mode="after")
    def validate_preview(self):
        """Validate unsaved content at the request boundary, returning HTTP 422."""
        if self.content is not None:
            QueryRuleDraft(scope=self.scope, content=self.content, name="Preview", reason="Preview")
        return self


class QueryRuleSampleSearch(_StrictDocBase):
    """Search authorized ready samples compatible with a policy's scope."""

    scope: QueryRuleScope
    search: str = Field(default="", max_length=200)
    page: int = Field(default=1, ge=1)


class QueryRuleSampleSummary(_StrictDocBase):
    """Identify a candidate sample without exposing its finding data."""

    id: str
    name: str
    asp_id: str | None = None
    subpanel_id: str | None = None


class QueryRuleSampleSearchResult(_StrictDocBase):
    """Return a page of authorized samples."""

    items: list[QueryRuleSampleSummary]
    total: int
    page: int
    per_page: int


class QueryRuleGroupOption(_StrictDocBase):
    """Identify an active assay group for authoring."""

    id: str
    name: str


class QueryRuleAssayOption(_StrictDocBase):
    """Identify an active assay and its associated subpanels."""

    id: str
    group: str
    category: str
    subpanels: list[str]


class QueryRuleOptions(_StrictDocBase):
    """Expose registered choices without unrestricted collection documents."""

    groups: list[QueryRuleGroupOption]
    assays: list[QueryRuleAssayOption]
    conditions: dict[str, Any] = Field(default_factory=dict)


class QueryRuleResolution(_StrictDocBase):
    """Expose effective settings and the published versions that supplied them."""

    scope: QueryRuleScope
    evidence_mode: str | None
    exceptions: list[dict[str, Any]]
    lineage: list[dict[str, Any]]
    compiled_conditions: list[dict[str, Any]] = Field(default_factory=list)
    requires_sample_context: bool = False


class QueryRuleFindingSummary(_StrictDocBase):
    """Identify a finding added or removed by a proposed query policy."""

    id: str
    label: str


class QueryRuleSampleResult(_StrictDocBase):
    """Compare exact selection counts with bounded finding identity lists."""

    sample: QueryRuleSampleSummary
    analysis: str
    intent: str
    persisted: Literal[False] = False
    published_count: int
    draft_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    added: list[QueryRuleFindingSummary]
    removed: list[QueryRuleFindingSummary]
    display_limit: int
    published_policy: QueryRuleResolution
    draft_policy: QueryRuleResolution
    published_query: dict[str, Any]
    draft_query: dict[str, Any]
    post_filters: list[str]
