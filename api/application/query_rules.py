"""Resolve and govern hierarchical finding-selection policies."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal

from api.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    FindingQueryPolicy,
    SnvQueryPolicy,
    exception_payload,
    resolved_query_policy,
)
from api.contracts.schemas.query_rules import (
    QueryConditionTest,
    QueryRuleContent,
    QueryRuleDoc,
    QueryRuleDraft,
    QueryRuleResolution,
    QueryRuleScope,
    QueryRuleTransition,
    QueryRuleUpdate,
)
from api.domain.common.errors import api_error
from api.domain.query_conditions import (
    compile_condition,
    condition_catalog,
    has_filter_references,
    matches_condition,
)


def effective_policy(
    service: Any,
    analysis: str,
    sample: dict,
    *,
    assay_group: str | None = None,
    intent: str = "somatic",
) -> SnvQueryPolicy | FindingQueryPolicy:
    """Resolve an injected policy service; standalone workflows use release defaults.

    Args:
        service: Workflow's query-rule service; None for explicit offline workflows.
        analysis: Implemented query namespace.
        sample: Sample or scope mapping with assay and subpanel identifiers.
        assay_group: Resolved ASPC group, overriding the sample's group when supplied.
        intent: Somatic or germline query intent.

    Returns:
        Validated typed policy for the requested sample scope.
    """
    if service is None:
        return getattr(CLINICAL_QUERY_POLICY, analysis)
    return service.policy(
        analysis=analysis,
        assay_group=assay_group or sample.get("asp_group"),
        asp_id=sample.get("asp_id"),
        subpanel_id=sample.get("subpanel_id") or "base",
        intent=intent,
    )


class QueryRuleService:
    """Manage policies and apply explicit overrides from broad to narrow scopes."""

    def __init__(
        self,
        repository: Any,
        groups: Any = None,
        assays: Any = None,
        subpanels: Any = None,
    ) -> None:
        """Bind policy persistence and the registries used to validate authoring scopes.

        Args:
            repository: Policy repository; reads must return only published ancestors.
            groups: Assay-group registry for authoring validation.
            assays: ASP registry for group membership validation.
            subpanels: Assay/subpanel association registry.
        """
        self.repository = repository
        self.groups = groups
        self.assays = assays
        self.subpanels = subpanels

    @classmethod
    def from_store(cls, store: Any) -> "QueryRuleService":
        """Construct the service from explicitly registered runtime repositories.

        Args:
            store: Runtime container exposing policy and clinical registry repositories.

        Returns:
            Service bound to the deployment's application database.
        """
        return cls(
            store.query_rule_repository,
            store.assay_group_repository,
            store.assay_panel_repository,
            store.assay_subpanel_repository,
        )

    def validate_scope(self, scope: QueryRuleScope) -> None:
        """Reject unknown or mismatched clinical scopes before saving or previewing.

        Args:
            scope: Group and optional assay/subpanel selected by the operator.

        Raises:
            AppError: A registry record is absent, inactive or belongs to another group.
        """
        if scope.assay_group is None:
            return
        group = self.groups.get(scope.assay_group)
        if not group or not group.get("is_active", True):
            raise api_error(422, "Choose an active registered assay group")
        if scope.asp_id:
            assay = self.assays.get_asp(scope.asp_id)
            if (
                not assay
                or assay.get("asp_group") != scope.assay_group
                or not assay.get("is_active", True)
            ):
                raise api_error(422, "Assay must belong to the selected group and be active")
            category = "rna" if scope.analysis == "fusion" else "dna"
            if assay.get("asp_category") != category:
                raise api_error(422, "Analysis is incompatible with the assay category")
        if scope.subpanel_id and scope.subpanel_id != "base":
            panel = self.subpanels.get_current(scope.asp_id, scope.subpanel_id)
            if (
                not panel
                or not panel.get("is_active", True)
                or not panel.get("definition_is_active", True)
            ):
                raise api_error(422, "Choose an active subpanel associated with the assay")

    def list(self) -> dict:
        """Return retained versions without exposing persistence result objects.

        Returns:
            Items envelope containing policy versions across lifecycle states.
        """
        return {"items": self.repository.list()}

    def options(self) -> dict:
        """Return active groups, assays and their available subpanel scopes.

        Returns:
            Group labels and assay identities/category/group/subpanel choices.
            Only named subpanels are offered; base denotes no specific subpanel.
        """
        return {
            "conditions": self.condition_options(),
            "groups": [
                {"id": g["group_id"], "name": g.get("display_name", g["group_id"])}
                for g in self.groups.list()
                if g.get("is_active", True)
            ],
            "assays": [
                {
                    "id": a["asp_id"],
                    "group": a["asp_group"],
                    "category": a["asp_category"],
                    "subpanels": [
                        *[
                            p["subpanel_id"]
                            for p in self.subpanels.list_for_assay(a["asp_id"], active_only=True)
                            if p["subpanel_id"] != "base"
                        ],
                    ],
                }
                for a in self.assays.get_all_asps(is_active=True)
            ],
        }

    def condition_options(self) -> dict:
        """Return field choices and references to the active sample filter profile.

        Returns:
            An isolated authoring catalog with no copied gene lists or filter values.
        """
        catalog = deepcopy(condition_catalog())
        for analysis, fields in catalog["fields"].items():
            for field in fields:
                path = field["path"]
                if path in {
                    "genes",
                    "gene1",
                    "gene2",
                    "genes.gene",
                    "INFO.selected_CSQ.SYMBOL",
                    "INFO.ANN.Gene_Name",
                    "INFO.MANE_ANN.Gene_Name",
                }:
                    if not (analysis == "fusion" and path == "genes"):
                        field["value_role"] = "gene"
                if field["filter_references"]:
                    field["hint"] = (
                        "Reference the active sample filter, or enter a literal manually. Reference values are resolved when the rule runs."
                    )
        return catalog

    def test_condition(self, request: QueryConditionTest) -> dict:
        """Test caller-provided synthetic records without reading any stored finding.

        Args:
            request: Analysis, validated condition and up to fifty example documents.

        Returns:
            Compiled predicate and match results in input order.
        """
        condition = request.condition.model_dump()
        return {
            "predicate": compile_condition(condition, request.analysis),
            "matches": [
                matches_condition(condition, request.analysis, document)
                for document in request.documents
            ],
        }

    def resolve(
        self,
        scope: QueryRuleScope,
        override: QueryRuleContent | None = None,
        *,
        publication: dict | None = None,
    ) -> QueryRuleResolution:
        """Resolve explicit fields through group, assay and subpanel published policies.

        Args:
            scope: Exact request scope, including analysis and intent.
            override: Optional unsaved leaf policy for authoring preview only.
            publication: Candidate ancestor publication for descendant validation only.

        Returns:
            Effective evidence mode, exceptions and ordered source-version lineage.

        Raises:
            AppError: More than one published version exists at a scope.
        """
        baseline = getattr(CLINICAL_QUERY_POLICY, scope.analysis)
        mode = (
            baseline.policy_for(assay_group=scope.assay_group, intent=scope.intent)
            if scope.analysis == "snv"
            else None
        )
        exceptions = [
            exception_payload(e)
            for e in baseline.exceptions
            if e.applies_to(
                assay_group=scope.assay_group,
                asp_id=scope.asp_id or "",
                subpanel_id=scope.subpanel_id or "",
                intent=scope.intent,
            )
        ]
        lineage = [
            {"source": "default", "version": None, "fields": ["evidence_mode", "exceptions"]}
        ]
        seen = set()

        def compose(content, inherited):
            """Combine local exceptions with parents without modifying either list.

            Args:
                content: Validated local content; null exceptions inherit unchanged.
                inherited: Effective ancestor exceptions in hierarchy order.

            Returns:
                Effective exceptions for the next hierarchy level.

            Raises:
                AppError: An extension reuses an inherited identifier.
            """
            if content.exceptions is None:
                return inherited
            if content.exception_mode == "replace":
                return content.exceptions
            inherited_ids = {item["id"] for item in inherited}
            if any(item["id"] in inherited_ids for item in content.exceptions):
                raise api_error(
                    422, "Extended exceptions must use identifiers distinct from inherited rules"
                )
            return [*inherited, *content.exceptions]

        rows = self.repository.published_for(scope.model_dump())
        if publication is not None:
            rows = [r for r in rows if r["scope_key"] != publication["scope_key"]] + [publication]
        for row in sorted(
            rows,
            key=lambda r: sum(
                bool(r["scope"].get(key)) for key in ("assay_group", "asp_id", "subpanel_id")
            ),
        ):
            doc = QueryRuleDoc.model_validate(row)
            if override is not None and doc.scope_key == scope.key():
                continue
            if doc.scope_key in seen:
                raise api_error(409, "Ambiguous published query policy")
            seen.add(doc.scope_key)
            fields = []
            if doc.content.evidence_mode is not None:
                mode = doc.content.evidence_mode
                fields.append("evidence_mode")
            if doc.content.exceptions is not None:
                exceptions = compose(doc.content, exceptions)
                fields.append("exceptions")
            lineage.append(
                {
                    "source": doc.scope_key,
                    "version": doc.version,
                    "revision": doc.revision,
                    "fields": fields,
                    "exception_mode": doc.content.exception_mode,
                }
            )
        if override is not None:
            if override.evidence_mode is not None:
                mode = override.evidence_mode
            if override.exceptions is not None:
                exceptions = compose(override, exceptions)
            lineage.append(
                {"source": "preview", "version": None, "exception_mode": override.exception_mode}
            )
        # Transitional combined SNV workflow: retain the somatic evidence branch,
        # while evaluating the independently resolved germline exceptions alongside it.
        if scope.analysis == "snv" and scope.intent == "somatic":
            germline_scope = QueryRuleScope.model_validate(
                {**scope.model_dump(), "intent": "germline"}
            )
            germline = self.resolve(germline_scope)
            exceptions = [
                *exceptions,
                *[{**item, "id": "germline__" + item["id"]} for item in germline.exceptions],
            ]
            if germline.exceptions or len(germline.lineage) > 1:
                lineage.extend(
                    {
                        **entry,
                        "intent": "germline",
                        "fields": ["exceptions"],
                        "application": "somatic_snv_exceptions",
                    }
                    for entry in germline.lineage
                )
        return QueryRuleResolution(
            scope=scope,
            evidence_mode=mode,
            exceptions=exceptions,
            lineage=lineage,
            compiled_conditions=[
                {
                    "id": item["id"],
                    "mode": item["mode"],
                    "predicate": compile_condition(item["condition"], scope.analysis),
                }
                for item in exceptions
                if "condition" in item and not has_filter_references(item["condition"])
            ],
            requires_sample_context=any(
                has_filter_references(item.get("condition")) for item in exceptions
            ),
        )

    def policy(
        self,
        *,
        analysis: str,
        assay_group: str,
        asp_id: str | None,
        subpanel_id: str | None,
        intent: str = "somatic",
    ) -> SnvQueryPolicy | FindingQueryPolicy:
        """Resolve a runtime policy without weakening mandatory query scope predicates.

        Args:
            analysis: Lowercase supported finding namespace.
            assay_group: Registered group identifier resolved from the sample's ASPC.
            asp_id: Sample's ASP identifier, or None for group scope.
            subpanel_id: Sample's subpanel identifier, or None for all assay subpanels.
            intent: SNV intent; other analyses use somatic.

        Returns:
            Typed policy consumed by the existing domain query builder.
        """
        scope = QueryRuleScope(
            assay_group=assay_group,
            asp_id=asp_id or None,
            subpanel_id=subpanel_id or None,
            analysis=analysis,
            intent=intent,
        )
        result = self.resolve(scope)
        return resolved_query_policy(analysis, result.evidence_mode, result.exceptions)

    def create(self, payload: QueryRuleDraft, actor: str) -> dict:
        """Create a new draft release for a validated scope and record its author.

        Args:
            payload: Validated scope and explicit overrides, including the change reason.
            actor: Authenticated account name; never supplied by draft content.

        Returns:
            Persisted draft with identity, version, revision and timestamps.

        Raises:
            AppError: Scope is unavailable or another draft claimed the version number.
        """
        self.validate_scope(payload.scope)
        self.resolve(payload.scope, payload.content)
        now = datetime.now(timezone.utc)
        document = {
            **payload.model_dump(),
            "scope_key": payload.scope.key(),
            "version": self.repository.next_version(payload.scope.key()),
            "revision": 1,
            "status": "draft",
            "created_by": actor,
            "updated_by": actor,
            "created_on": now,
            "updated_on": now,
        }
        return self.repository.create(
            QueryRuleDoc.model_validate(document).model_dump(by_alias=True, exclude_none=True)
        )

    def update(self, identifier: str, payload: QueryRuleUpdate, actor: str) -> dict:
        """Replace draft content using optimistic concurrency and immutable scope.

        Args:
            identifier: Serialized identity of the draft being edited.
            payload: Replacement content and the revision inspected by the operator.
            actor: Authenticated editor's account name.

        Returns:
            Updated draft with its incremented revision.

        Raises:
            AppError: Scope changes, registry validation, stale edits or lifecycle state
                prevent the update.
        """
        self.validate_scope(payload.scope)
        self.resolve(payload.scope, payload.content)
        current = self.repository.get(identifier)
        if not current:
            raise api_error(404, "Query rule version not found")
        if current["scope_key"] != payload.scope.key():
            raise api_error(422, "An existing rule version cannot change scope")
        values = payload.model_dump(exclude={"expected_revision", "scope"})
        values.update(updated_by=actor, updated_on=datetime.now(timezone.utc))
        return self.repository.change(identifier, payload.expected_revision, "draft", values, actor)

    def transition(
        self,
        identifier: str,
        action: Literal["approve", "publish", "retire"],
        payload: QueryRuleTransition,
        actor: str,
    ) -> dict:
        """Approve independently, publish atomically or retire a release with a reason.

        Args:
            identifier: Serialized identity of the saved version.
            action: Approve, publish or retire operation selected by the authorized route.
            payload: Inspected revision and the operator's explanation.
            actor: Authenticated reviewer, publisher or withdrawing operator.

        Returns:
            Version in its successor lifecycle state.

        Raises:
            AppError: Version is absent, stale, unavailable, in the wrong state or
                submitted for approval by its creator or latest editor.
        """
        current = self.repository.get(identifier)
        if not current:
            raise api_error(404, "Query rule version not found")
        QueryRuleDoc.model_validate(current)
        if action != "retire":
            self.validate_scope(QueryRuleScope.model_validate(current["scope"]))
            self.resolve(
                QueryRuleScope.model_validate(current["scope"]),
                QueryRuleContent.model_validate(current["content"]),
            )
        before, after = {
            "approve": ("draft", "approved"),
            "publish": ("approved", "published"),
            "retire": ("published", "retired"),
        }[action]
        if action == "approve" and actor in {current["created_by"], current["updated_by"]}:
            raise api_error(403, "Another clinical reviewer must approve this draft")
        values = {
            "status": after,
            "reason": payload.reason,
            "updated_on": datetime.now(timezone.utc),
            "updated_by": actor,
        }
        if action == "approve":
            values["approved_by"] = actor
        if action == "publish":
            for descendant in self.repository.list():
                child_scope = descendant["scope"]
                if descendant["status"] == "published" and all(
                    value is None or child_scope.get(key) == value
                    for key, value in current["scope"].items()
                ):
                    self.resolve(QueryRuleScope.model_validate(child_scope), publication=current)
            values.update(published_by=actor, published_on=datetime.now(timezone.utc))
        return self.repository.change(identifier, payload.expected_revision, before, values, actor)

    def delete_draft(self, identifier: str, payload: QueryRuleTransition, actor: str) -> dict:
        """Delete an inspected draft with an audited explanation.

        Args:
            identifier: Draft version ObjectId.
            payload: Expected revision and deletion reason.
            actor: Authenticated editor authorized by the route.

        Returns:
            Deleted draft; published and approved versions cannot be deleted.
        """
        return self.repository.delete_draft(
            identifier, payload.expected_revision, actor, payload.reason
        )

    def revisions(self, identifier: str) -> list[dict]:
        """Read verified immutable history for a retained version.

        Args:
            identifier: Rule version ObjectId.

        Returns:
            Newest-first snapshots.

        Raises:
            AppError: Version does not exist.
        """
        if not self.repository.get(identifier):
            raise api_error(404, "Query rule version not found")
        return self.repository.history.list_for_version(identifier)
