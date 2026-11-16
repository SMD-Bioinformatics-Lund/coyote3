# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Governed clinical rule review and publication."""

from __future__ import annotations

from typing import Any

from coyote.application.common.protected_records import reject_system_managed_change
from coyote.application.reporting.clinical_rules.validation import (
    content_hash,
    validate_rule_set,
)
from coyote.application.resources.availability import require_active_group
from coyote.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
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
from .records import RuleRecords


class RuleLifecycle:
    """Coordinate independent review, publication, reopening and retirement."""

    def __init__(
        self, records: RuleRecords, catalog: RuleScopeCatalog, assignments: ReviewAssignments
    ) -> None:
        """Bind record transitions, scope validation and independent reviewers."""
        self.records = records
        self.catalog = catalog
        self.assignments = assignments

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
        document = self.records.get(document_id)
        if document.status not in {
            ClinicalRuleStatus.SUBMITTED,
            ClinicalRuleStatus.IN_CLINICAL_REVIEW,
            ClinicalRuleStatus.APPROVED,
        }:
            raise api_error(409, "Only submitted, in-review or approved versions can be reopened")
        if document.revision != payload.revision:
            raise api_error(409, "The rule set changed. Reload before editing again.")
        return self.records.transition(
            document_id,
            expected_revision=payload.revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={document.status.value},
            status=ClinicalRuleStatus.DRAFT,
            extra={"review": {}, "content_hash": None, "active": False, "updated_by": actor},
        )

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
        document = self.records.get(document_id)
        self.catalog.validate(ClinicalRuleDraftCreate(scope=document.scope))
        validation = validate_rule_set(document)
        reject_system_managed_change(document.model_dump(), resource="clinical rule set")
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        now = utc_now()
        reviewer = self.assignments.validate(
            payload.assignee,
            "clinical_rules:clinical_review",
            label="clinical reviewer",
            exclude=actor,
        )
        if reviewer == str(document.updated_by).strip().lower():
            raise api_error(
                409, "The latest content editor cannot be the assigned clinical reviewer"
            )
        result = self.records.transition(
            document_id,
            expected_revision=document.revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"draft"},
            status=ClinicalRuleStatus.SUBMITTED,
            extra={
                "review.submitted_by": actor,
                "review.submitted_at": now,
                "review.clinical_reviewer": reviewer,
            },
        )
        document = ClinicalRuleSetDoc.model_validate(result)
        self.assignments.notify(
            recipient=reviewer,
            title="Clinical rule review requested",
            message=f"{actor} submitted '{document.name}' for your clinical review.",
            document=document,
            actor=actor,
        )
        return result

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
        document = self.records.get(document_id)
        if document.review.clinical_reviewer != actor:
            raise api_error(409, "This clinical review is assigned to another user")
        if actor in {document.updated_by, document.review.submitted_by}:
            raise api_error(409, "The editor or submitter cannot review this version")
        result = self.records.transition(
            document_id,
            expected_revision=document.revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"submitted"},
            status=ClinicalRuleStatus.IN_CLINICAL_REVIEW,
            extra={"review.clinical_reviewer": actor},
        )
        return result

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
        document = self.records.get(document_id)
        if actor in {document.updated_by, document.review.submitted_by}:
            raise api_error(409, "The latest content editor cannot clinically approve this version")
        if document.review.clinical_reviewer != actor:
            raise api_error(409, "This clinical review is assigned to another user")
        publisher = None
        if payload.approve:
            publisher = self.assignments.validate(
                payload.publisher, "clinical_rules:publish", label="publisher"
            )
        status = ClinicalRuleStatus.APPROVED if payload.approve else ClinicalRuleStatus.REJECTED
        now = utc_now()
        result = self.records.transition(
            document_id,
            expected_revision=document.revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"in_clinical_review"},
            status=status,
            extra={
                "review.clinical_reviewer": actor,
                "review.clinical_decision_at": now,
                "review.clinical_decision_reason": payload.reason,
                "review.publisher": publisher,
            },
        )
        decided = ClinicalRuleSetDoc.model_validate(result)
        author = document.review.submitted_by or document.created_by
        self.assignments.notify(
            recipient=author,
            title="Clinical rule review approved"
            if payload.approve
            else "Clinical rule review rejected",
            message=f"{actor} {('approved' if payload.approve else 'rejected')} '{decided.name}'. {payload.reason}"
            + (" You are assigned to publish this version." if publisher == author else ""),
            document=decided,
            actor=actor,
        )
        if payload.approve and publisher != author:
            self.assignments.notify(
                recipient=publisher,
                title="Clinical rule publication requested",
                message=f"{actor} clinically approved '{decided.name}' and assigned it for publication.",
                document=decided,
                actor=actor,
            )
        return result

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
        document = self.records.get(document_id)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        reject_system_managed_change(document.model_dump(), resource="clinical rule set")
        if not document.review.clinical_reviewer:
            raise api_error(409, "Clinical approval is required before publication")
        if document.review.clinical_reviewer == document.updated_by:
            raise api_error(409, "Clinical approval must be independent of the latest editor")
        if document.review.publisher != actor:
            raise api_error(409, "This publication is assigned to another user")
        panel = next(
            (p for p in self.catalog.panels() if p["asp_id"] == document.scope.asp_id), None
        )
        if panel is None:
            raise api_error(409, "Assay is unavailable for publication")
        require_active_group(self.catalog.assay_panel_repository, panel["asp_group"])
        now = utc_now()
        digest = content_hash(document)
        event = {
            "action": "published",
            "actor": actor,
            "occurred_at": now,
            "reason": payload.reason or None,
        }
        updated = self.records.repository.publish(
            document_id,
            expected_revision=document.revision,
            changes={
                "status": "published",
                "active": True,
                "published_at": now,
                "published_by": actor,
                "effective_from": now,
                "updated_at": now,
                "content_hash": digest,
            },
            event=event,
        )
        if updated is None:
            raise api_error(409, "Only an approved clinical rule set can be published")
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        if parsed.created_by != actor:
            self.assignments.notify(
                recipient=parsed.created_by,
                title="Clinical rule set published",
                message=f"{actor} published '{parsed.name}'.",
                document=parsed,
                actor=actor,
            )
        return parsed.model_dump(mode="python", by_alias=True)

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
        if not payload.reason:
            raise api_error(400, "A retirement reason is required")
        now = utc_now()
        return self.records.transition(
            document_id,
            expected_revision=self.records.get(document_id).revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"published"},
            status=ClinicalRuleStatus.RETIRED,
            extra={"active": False, "retired_at": now, "retired_by": actor},
        )
