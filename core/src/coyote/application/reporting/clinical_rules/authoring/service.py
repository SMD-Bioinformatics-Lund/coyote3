# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Clinical rule draft authoring, inspection and governed lifecycle orchestration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from coyote.application.classification.bulk_annotation_rules import (
    render_bulk_annotation,
)
from coyote.application.common.protected_records import reject_system_managed_change
from coyote.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote.application.reporting.clinical_rules.facts import PreparedReportContext
from coyote.application.reporting.clinical_rules.validation import (
    content_hash,
    validate_rule_set,
)
from coyote.contracts.schemas.clinical_rules import (
    BulkAnnotationPreviewRequest,
    ClinicalRuleConfiguration,
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleReopenRequest,
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
    ClinicalRuleTransition,
)
from coyote.domain.common.errors import api_error
from coyote.domain.common.reporting import (
    utc_now,
)

from .assignments import ReviewAssignments
from .catalog import RuleScopeCatalog
from .lifecycle import RuleLifecycle
from .records import RuleRecords


def _new_rule_set_blocks() -> list[dict[str, Any]]:
    """Return the first editable section for a newly authored rule set.

    A draft must open into the visual builder rather than an empty workspace.
    The starter rule is disabled until its author has supplied report wording
    and deliberately enabled it.
    """
    return [
        {
            "block_id": "report_section_1",
            "name": "Report section 1",
            "analysis": None,
            "evaluation": {"mode": "once", "collection": None},
            "section": "Report section 1",
            "section_order": 100,
            "block_order": 10,
            "show_heading": True,
            "match_strategy": "at_most_one",
            "rules": [
                {
                    "rule_id": "report_section_1_rule_1",
                    "name": "Report section 1 rule 1",
                    "order": 10,
                    "enabled": False,
                    "condition": None,
                    "output": [{"type": "text", "value": "Add report wording."}],
                    "references": [],
                }
            ],
        }
    ]


class ClinicalRuleAuthoringService:
    """Manage rule drafts, independent clinical approval, and releases."""

    @classmethod
    def from_store(
        cls, store: Any, *, notification_service: Any | None = None
    ) -> "ClinicalRuleAuthoringService":
        """Bind authoring to rule, revision, assay, and optional identity repositories.

        Args:
            store: Repository provider; user and role repositories may be absent.
            notification_service: Optional delivery service for review assignments.

        Returns:
            Authoring service bound to the supplied repositories and delivery service.
        """
        return cls(
            store.clinical_rule_set_repository,
            revision_repository=store.clinical_rule_revision_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_diagnosis_repository=store.assay_diagnosis_repository,
            assay_group_repository=getattr(store, "assay_group_repository", None),
            user_repository=getattr(store, "user_repository", None),
            role_repository=getattr(store, "roles_repository", None),
            notification_service=notification_service,
        )

    def __init__(
        self,
        repository: Any,
        *,
        revision_repository: Any | None = None,
        assay_panel_repository: Any | None = None,
        assay_diagnosis_repository: Any | None = None,
        assay_group_repository: Any | None = None,
        user_repository: Any | None = None,
        role_repository: Any | None = None,
        notification_service: Any | None = None,
    ) -> None:
        """Configure persistence and optional governance integrations.

        Args:
            repository: Stores rule versions and conditional lifecycle updates.
            revision_repository: Reads revision history; None disables history lookup.
            assay_panel_repository: Optional active-assay validation and option source.
            assay_diagnosis_repository: Registered scopes; required when validating an assay.
            assay_group_repository: Registered biological hierarchy for annotation options.
            user_repository: Optional active-user lookup for assignments.
            role_repository: Optional permission-to-role lookup for assignments.
            notification_service: Optional sender of review and publication requests.
        """
        self.repository = repository
        self.revision_repository = revision_repository
        self.assignments = ReviewAssignments(
            user_repository=user_repository,
            role_repository=role_repository,
            notification_service=notification_service,
        )
        self.catalog = RuleScopeCatalog(
            assay_panel_repository=assay_panel_repository,
            assay_diagnosis_repository=assay_diagnosis_repository,
            assay_group_repository=assay_group_repository,
            assignments=self.assignments,
        )
        self.records = RuleRecords(repository)
        self.lifecycle = RuleLifecycle(self.records, self.catalog, self.assignments)

    def list(
        self, *, status: str | None, search: str | None, page: int, per_page: int
    ) -> dict[str, Any]:
        """Read a page of rule versions using repository filters.

        Args:
            status: Optional lifecycle status filter.
            search: Optional repository search text.
            page: One-based page number used to calculate the offset.
            per_page: Maximum versions requested per page.

        Returns:
            Items, requested page and page size, and total matching count.
        """
        skip = (page - 1) * per_page
        rows, total = self.repository.list_rule_sets(
            status=status, search=search, skip=skip, limit=per_page
        )
        return {"items": rows, "page": page, "per_page": per_page, "total": total}

    def versions(self, rule_set_id: str) -> list[dict[str, Any]]:
        """Read the repository's version history for one logical rule set.

        Args:
            rule_set_id: Logical rule-set identifier, not a version document ID.

        Returns:
            Stored versions in repository order.
        """
        return self.repository.list_versions(rule_set_id)

    def get(self, document_id: str) -> dict[str, Any]:
        """Read a canonical rule version with persistence field aliases.

        Args:
            document_id: Version document identifier.

        Returns:
            Parsed document serialized with Python values and aliases.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        return self.records.get(document_id).model_dump(mode="python", by_alias=True)

    def export(self, document_id: str, *, include_metadata: bool = False) -> dict[str, Any]:
        """Export portable rules, optionally including the stored version's metadata.

        Args:
            document_id: Version document identifier to read.
            include_metadata: Include identity, lifecycle, versions and audit fields
                when True; defaults to authored configuration only.

        Returns:
            Configuration fields or the full governed document, using Python values
            and persistence aliases for transport serialization.

        Raises:
            AppError: The requested version does not exist.
        """
        document = self.records.get(document_id)
        return document.model_dump(
            mode="python",
            by_alias=True,
            include=None if include_metadata else set(ClinicalRuleConfiguration.model_fields),
        )

    def revisions(self, document_id: str) -> list[dict[str, Any]]:
        """Read revision history after confirming the version exists.

        Args:
            document_id: Version document identifier.

        Returns:
            Repository revision rows, or an empty list without revision storage.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        self.records.get(document_id)
        if self.revision_repository is None:
            return []
        return self.revision_repository.list_for_version(document_id)

    def revision(self, document_id: str, revision: int) -> dict[str, Any]:
        """Read one retained revision of an existing rule version.

        Args:
            document_id: Version document identifier.
            revision: Revision number to retrieve.

        Returns:
            Stored revision document.

        Raises:
            AppError: With status 404 for an absent version or revision,
                including when revision storage is not configured.
        """
        self.records.get(document_id)
        document = (
            self.revision_repository.get_revision(document_id, revision)
            if self.revision_repository is not None
            else None
        )
        if document is None:
            raise api_error(404, "Clinical rule-set revision was not found")
        return document

    def create_draft(self, payload: ClinicalRuleDraftCreate, *, actor: str) -> dict[str, Any]:
        """Create a fresh draft or clone a published or rejected version.

        Args:
            payload: New scope/name or source version with optional scope/name overrides.
            actor: Login recorded as creator, latest editor, and lifecycle actor.

        Returns:
            Inserted draft at revision one with reset review and release metadata.

        Raises:
            AppError: With status 400 for missing new-draft scope/name, 404 for a
                missing source, or 409 for an invalid source status or assay scope.
            ValidationError: The assembled draft fails canonical schema validation.

        Notes:
            Allocates the next content version and records a draft-created audit event.
        """
        now = utc_now()
        if payload.source_version_id:
            source = self.records.get(payload.source_version_id)
            if source.status not in {ClinicalRuleStatus.PUBLISHED, ClinicalRuleStatus.REJECTED}:
                raise api_error(
                    409, "A draft can be cloned only from a published or rejected version"
                )
            document = source.model_dump(mode="python", by_alias=True)
            document.pop("_id", None)
            target_scope = payload.scope or source.scope
            self.catalog.validate(
                ClinicalRuleDraftCreate(scope=target_scope, name=payload.name or source.name),
                allow_unregistered=True,
            )
            target_rule_set_id = (
                f"{target_scope.asp_id}__{target_scope.diagnosis_id}__{target_scope.language}"
            )
            document.update(
                {
                    "rule_set_id": target_rule_set_id,
                    "scope": target_scope.model_dump(mode="python"),
                    "name": payload.name or source.name,
                    "content_version": self.repository.next_content_version(target_rule_set_id),
                    "revision": 1,
                    "status": "draft",
                    "active": False,
                    "change_summary": "",
                    "system_installed": False,
                    "review": {},
                    "lifecycle": [],
                    "created_at": now,
                    "created_by": actor,
                    "updated_at": now,
                    "updated_by": actor,
                    "published_at": None,
                    "published_by": None,
                    "effective_from": None,
                    "retired_at": None,
                    "retired_by": None,
                    "content_hash": None,
                    "provenance": {
                        "source": "template" if payload.source == "template" else payload.source,
                        "source_rule_set_id": source.rule_set_id,
                        "source_content_version": source.content_version,
                        "source_revision": source.revision,
                    },
                }
            )
        else:
            if payload.scope is None or not payload.name:
                raise api_error(400, "A new rule set requires scope and name")
            self.catalog.validate(payload, allow_unregistered=True)
            rule_set_id = (
                f"{payload.scope.asp_id}__{payload.scope.diagnosis_id}__{payload.scope.language}"
            )
            document = {
                "rule_set_id": rule_set_id,
                "schema_version": 1,
                "content_version": self.repository.next_content_version(rule_set_id),
                "revision": 1,
                "scope": payload.scope.model_dump(mode="python"),
                "name": payload.name,
                "status": "draft",
                "active": False,
                "analysis_declarations": {},
                "terminology": {},
                "blocks": _new_rule_set_blocks(),
                "test_cases": [],
                "references": [],
                "provenance": {"source": payload.source},
                "change_summary": "",
                "review": {},
                "lifecycle": [],
                "created_at": now,
                "created_by": actor,
                "updated_at": now,
                "updated_by": actor,
            }
        document["lifecycle"] = [{"action": "draft_created", "actor": actor, "occurred_at": now}]
        parsed = ClinicalRuleSetDoc.model_validate(document)
        saved = ClinicalRuleSetDoc.model_validate(
            self.repository.insert(
                parsed.model_dump(mode="python", by_alias=True, exclude_none=True),
                action="draft_created",
                actor=actor,
            )
        )
        return saved.model_dump(mode="python", by_alias=True)

    def import_draft(self, payload: ClinicalRuleImportRequest, *, actor: str) -> dict[str, Any]:
        """Import authored rules and assign fresh identity, version and audit metadata.

        Args:
            payload: Authored configuration or metadata-inclusive export, plus target
                scope and name. Stored document metadata is ignored on import.
            actor: Authenticated user to record as creator and updater.

        Returns:
            A new inactive draft with a server-allocated version and current timestamps.

        Raises:
            AppError: Configuration validation or target-scope validation fails.
        """
        managed_fields = set(ClinicalRuleSetDoc.model_fields) - set(
            ClinicalRuleConfiguration.model_fields
        )
        managed_fields.add("_id")
        try:
            source = ClinicalRuleConfiguration.model_validate(
                {key: value for key, value in payload.document.items() if key not in managed_fields}
            )
        except ValueError as exc:
            raise api_error(
                422, "Imported rule-set file is not a valid configuration", str(exc)
            ) from exc
        create = ClinicalRuleDraftCreate(scope=payload.scope, name=payload.name, source="api")
        now = utc_now()
        self.catalog.validate(create, allow_unregistered=True)
        target_rule_set_id = (
            f"{payload.scope.asp_id}__{payload.scope.diagnosis_id}__{payload.scope.language}"
        )
        document = source.model_dump(mode="python", by_alias=True)
        document.update(
            {
                "rule_set_id": target_rule_set_id,
                "scope": payload.scope.model_dump(mode="python"),
                "name": payload.name,
                "content_version": self.repository.next_content_version(target_rule_set_id),
                "revision": 1,
                "status": "draft",
                "active": False,
                "change_summary": "",
                "review": {},
                "lifecycle": [{"action": "draft_imported", "actor": actor, "occurred_at": now}],
                "system_installed": False,
                "created_at": now,
                "created_by": actor,
                "updated_at": now,
                "updated_by": actor,
                "published_at": None,
                "published_by": None,
                "effective_from": None,
                "retired_at": None,
                "retired_by": None,
                "content_hash": None,
                "provenance": {
                    "source": "import",
                    "source_rule_set_id": f"{source.scope.asp_id}__{source.scope.diagnosis_id}__{source.scope.language}",
                    "imported_schema_version": source.schema_version,
                    **{
                        f"source_{key}": value
                        for key in ("content_version", "revision")
                        if isinstance((value := payload.document.get(key)), int)
                        and (not isinstance(value, bool))
                        and (value > 0)
                    },
                },
            }
        )
        parsed = ClinicalRuleSetDoc.model_validate(document)
        saved = ClinicalRuleSetDoc.model_validate(
            self.repository.insert(
                parsed.model_dump(mode="python", by_alias=True, exclude_none=True),
                action="draft_imported",
                actor=actor,
            )
        )
        return saved.model_dump(mode="python", by_alias=True)

    def update_draft(
        self, document_id: str, payload: ClinicalRuleDraftUpdate, *, actor: str
    ) -> dict[str, Any]:
        """Validate and save non-null draft changes against the expected revision.

        Args:
            document_id: Draft version identifier.
            payload: Changed content and revision used for the conditional write.
            actor: Login recorded as latest content editor and audit actor.

        Returns:
            Saved canonical draft with its content hash cleared.

        Raises:
            AppError: With status 404 for a missing version or 409 when the
                repository refuses the conditional draft update.
            ValidationError: The proposed document fails canonical validation.

        Notes:
            A scope edit requires an available compatible assay and diagnosis.
            Changing the logical scope allocates its next content version while
            retaining the document ID and revision chain. Authored conditions
            and embedded case facts are preserved for explicit review.
        """
        changes = payload.model_dump(exclude={"revision"}, exclude_none=True, mode="python")
        changes.update({"updated_at": utc_now(), "updated_by": actor, "content_hash": None})
        current = self.records.get(document_id)
        candidate = current.model_dump(mode="python", by_alias=True)
        reject_system_managed_change(candidate, resource="reporting rule")
        if payload.scope is not None:
            if current.status != ClinicalRuleStatus.DRAFT:
                raise api_error(409, "Only a draft can change its assay association")
            self.catalog.validate(ClinicalRuleDraftCreate(scope=payload.scope))
            target_id = (
                f"{payload.scope.asp_id}__{payload.scope.diagnosis_id}__{payload.scope.language}"
            )
            changes["rule_set_id"] = target_id
            if target_id != current.rule_set_id:
                changes["content_version"] = self.repository.next_content_version(target_id)
        candidate.update({**deepcopy(changes), "revision": payload.revision + 1})
        ClinicalRuleSetDoc.model_validate(candidate)
        updated = self.repository.update_draft(
            document_id, expected_revision=payload.revision, changes=changes, actor=actor
        )
        if updated is None:
            raise api_error(
                409,
                "The clinical rule draft changed while it was being edited",
                hint="Reload the draft and reconcile the newer revision before saving.",
            )
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        return parsed.model_dump(mode="python", by_alias=True)

    def delete_draft(self, document_id: str, *, expected_revision: int, actor: str) -> None:
        """Discard a pre-publication version while preserving released versions and audit."""
        document = self.records.get(document_id)
        reject_system_managed_change(document.model_dump(), resource="reporting rule")
        if (
            document.status
            not in {
                ClinicalRuleStatus.DRAFT,
                ClinicalRuleStatus.SUBMITTED,
                ClinicalRuleStatus.IN_CLINICAL_REVIEW,
                ClinicalRuleStatus.APPROVED,
                ClinicalRuleStatus.REJECTED,
            }
            or document.published_at is not None
        ):
            raise api_error(409, "Only an unpublished clinical rule version can be deleted")
        deleted = self.repository.delete_draft(
            document_id, expected_revision=expected_revision, actor=actor
        )
        if deleted is None:
            raise api_error(
                409,
                "The clinical rule draft changed while it was being deleted. Reload and try again.",
            )

    def validate(self, document_id: str) -> dict[str, Any]:
        """Validate a stored version's structure and semantics without embedded test gates.

        Args:
            document_id: Rule version identifier.

        Returns:
            Validity, errors, and warnings as Python values.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        return validate_rule_set(self.records.get(document_id)).model_dump(mode="python")

    def preview_bulk_annotation(
        self, document_id: str, facts: BulkAnnotationPreviewRequest
    ) -> dict[str, Any]:
        """Preview annotation wording against synthetic facts without database writes.

        Args:
            document_id: Saved version to evaluate, including an unpublished draft.
            facts: Safe finding values and explicitly selected tier.

        Returns:
            Matching rule ID and text, or null values for no match.

        Raises:
            AppError: Version is absent or its rules or output are invalid.
        """
        document = self.records.get(document_id)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        try:
            if facts.asp_group is None and self.catalog.assay_panel_repository is not None:
                panel = next(
                    (
                        panel
                        for panel in self.catalog.panels()
                        if panel.get("asp_id") == document.scope.asp_id
                    ),
                    None,
                )
                if panel and panel.get("asp_group"):
                    facts = facts.model_copy(update={"asp_group": panel["asp_group"]})
            return render_bulk_annotation(
                document, facts, groups=self.catalog.annotation_groups()
            ).model_dump(mode="python")
        except ValueError as exc:
            raise api_error(422, "Annotation preview failed", str(exc)) from exc

    def preview(self, document_id: str, facts: dict[str, Any]) -> dict[str, Any]:
        """Evaluate supplied facts against a version without persisting a report.

        Args:
            document_id: Rule version identifier, regardless of release status.
            facts: Data accepted by PreparedReportContext.

        Returns:
            Evaluation using all declared analyses and a freshly computed content hash.

        Raises:
            AppError: With status 404 when the version is absent.
            ValueError: Facts are invalid or rule evaluation/rendering fails.
        """
        document = self.records.get(document_id)
        context = PreparedReportContext.model_validate(facts)
        analyses = set(document.analysis_declarations)
        candidate = document.model_copy(update={"content_hash": content_hash(document)})
        return (
            ClinicalRuleEvaluator()
            .evaluate(context, candidate, reporting_analyses=analyses)
            .model_dump(mode="python")
        )

    def reopen_draft(
        self, document_id: str, payload: ClinicalRuleReopenRequest, *, actor: str
    ) -> dict[str, Any]:
        """Recall a submitted, in-review or approved version for editing.

        Args:
            document_id: Unpublished review-stage version to reopen without changing identity.
            payload: Revision seen by the editor and an audit reason.
            actor: Authorized editor recorded as the latest editor.

        Returns:
            Same content version at its next revision, with review metadata cleared.

        Raises:
            AppError: Version is absent, protected, stale or no longer in a review stage.

        Notes:
            Previous review remains in immutable revision/lifecycle history.
            The revision and source-state predicate fence concurrent review or publication.
        """
        return self.lifecycle.reopen_draft(document_id, payload, actor=actor)

    def submit(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        """Validate a draft, assign an independent reviewer, and request review.

        Args:
            document_id: Draft version identifier.
            payload: Reviewer assignee and lifecycle reason.
            actor: Submitting login, excluded from reviewer assignment.

        Returns:
            Submitted version after audit recording and optional reviewer notification.

        Raises:
            AppError: With status 404 for a missing version, 422 for rule errors,
                400 for no reviewer, or 409 for an invalid assignment or transition.

        Notes:
            Embedded cases are not required or executed. The write is fenced by the
            validated revision so a concurrent edit cannot enter review.
        """
        return self.lifecycle.submit(document_id, payload, actor=actor)

    def start_review(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        """Move a submitted version into review for its assigned reviewer.

        Args:
            document_id: Submitted version identifier.
            payload: Lifecycle reason; other transition fields are not used here.
            actor: Assigned clinical reviewer; neither content editor nor submitter.

        Returns:
            Version in clinical review, after audit recording.

        Raises:
            AppError: With status 404 for a missing version or 409 for a different
                reviewer, self-review, or refused lifecycle transition.
        """
        return self.lifecycle.start_review(document_id, payload, actor=actor)

    def clinical_decision(
        self, document_id: str, payload: ClinicalRuleDecision, *, actor: str
    ) -> dict[str, Any]:
        """Record the assigned reviewer's approval or rejection and notify its recipient.

        Args:
            document_id: Version currently in clinical review.
            payload: Decision and reason, plus an eligible publisher for approval.
            actor: Assigned reviewer login; editor and submitter cannot record either decision.

        Returns:
            Approved or rejected version with decision metadata.

        Raises:
            AppError: With status 404 for a missing version, 400 for no required
                publisher, or 409 for editor/reviewer, assignee, or state conflicts.

        Notes:
            Both outcomes notify the submitter, falling back to the draft creator.
            Approval also requests publication from the assigned publisher.
        """
        return self.lifecycle.clinical_decision(document_id, payload, actor=actor)

    def publish(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        """Validate and publish an independently reviewed version for its assigned publisher.

        Args:
            document_id: Approved version identifier.
            payload: Publication reason; assignee is not used here.
            actor: Login that must equal the assigned publisher.

        Returns:
            Active published version with content hash and UTC effective time.

        Raises:
            AppError: With status 404 for a missing version, 422 for rule errors,
                or 409 for approval, independence, publisher, or state conflicts.

        Notes:
            Audits publication and notifies the creator when different from the publisher.
            Requires valid rule semantics and an unchanged validated revision.
            Embedded cases are not required or executed.
        """
        return self.lifecycle.publish(document_id, payload, actor=actor)

    def retire(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        """Deactivate a published version with a recorded retirement reason.

        Args:
            document_id: Published version identifier.
            payload: Transition request containing a nonempty reason.
            actor: Login recorded as retiring actor.

        Returns:
            Retired, inactive version with retirement provenance.

        Raises:
            AppError: With status 400 for no reason or 409 for a refused transition.
        """
        return self.lifecycle.retire(document_id, payload, actor=actor)

    def authoring_options(self) -> dict[str, Any]:
        """Return authoring scopes and optional sentence wording for explicit draft insertion."""
        return self.catalog.options()

    def reviewer_options(self) -> dict[str, list[dict[str, str]]]:
        """List active users eligible for clinical review and publication.

        Returns:
            Clinical reviewer and publisher choices; empty without identity repositories.
        """
        return self.assignments.options()
