"""Governed authoring and publication workflows for clinical rule sets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from api.config.constants import ENVIRONMENT_OPTIONS
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
    ClinicalRuleTransition,
)
from api.domain.common.errors import api_error


def _now() -> datetime:
    """Read the current UTC time.

    Returns:
        Timezone-aware timestamp for lifecycle and provenance fields.
    """
    return datetime.now(timezone.utc)


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
            "match_strategy": "first_match",
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
        cls, store: Any, *, audit_service: Any | None = None
    ) -> "ClinicalRuleAuthoringService":
        """Bind authoring to rule, revision, assay, and optional identity repositories.

        Args:
            store: Repository provider; user and role repositories may be absent.
            audit_service: Optional recorder for lifecycle events.

        Returns:
            Authoring service without a notification service configured.
        """
        return cls(
            store.clinical_rule_set_repository,
            revision_repository=store.clinical_rule_revision_repository,
            audit_service=audit_service,
            assay_panel_repository=store.assay_panel_repository,
            user_repository=getattr(store, "user_repository", None),
            role_repository=getattr(store, "role_repository", None),
        )

    def __init__(
        self,
        repository: Any,
        *,
        revision_repository: Any | None = None,
        audit_service: Any | None = None,
        assay_panel_repository: Any | None = None,
        user_repository: Any | None = None,
        role_repository: Any | None = None,
        notification_service: Any | None = None,
    ) -> None:
        """Configure persistence and optional governance integrations.

        Args:
            repository: Stores rule versions and conditional lifecycle updates.
            revision_repository: Reads revision history; None disables history lookup.
            audit_service: Optional lifecycle event recorder.
            assay_panel_repository: Optional active-assay validation and option source.
            user_repository: Optional active-user lookup for assignments.
            role_repository: Optional permission-to-role lookup for assignments.
            notification_service: Optional sender of review and publication requests.
        """
        self.repository = repository
        self.revision_repository = revision_repository
        self.audit_service = audit_service
        self.assay_panel_repository = assay_panel_repository
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.notification_service = notification_service

    def authoring_options(self) -> dict[str, Any]:
        """Return active assay scopes available for new rule sets."""
        if self.assay_panel_repository is None:
            return {"assays": [], "condition_values": {}, **self.reviewer_options()}
        assays = []
        for panel in self.assay_panel_repository.get_all_asps(is_active=True):
            analyte = str(panel.get("asp_category") or "").lower()
            if analyte not in {"dna", "rna"}:
                continue
            asp_id = str(panel.get("asp_id") or "").strip()
            if not asp_id:
                continue
            assays.append(
                {
                    "asp_id": asp_id,
                    "display_name": str(panel.get("display_name") or asp_id),
                    "analyte": analyte,
                }
            )
        rows, _ = self.repository.list_rule_sets(limit=200)
        subpanels = sorted(
            {"base", *(str(row.get("scope", {}).get("subpanel_id") or "").strip() for row in rows)}
            - {""}
        )
        groups = sorted(
            {
                str(panel.get("asp_group") or "").strip()
                for panel in self.assay_panel_repository.get_all_asps(is_active=True)
            }
            - {""}
        )
        return {
            "assays": sorted(assays, key=lambda item: (item["display_name"], item["asp_id"])),
            "condition_values": {
                "sample.asp_id": [item["asp_id"] for item in assays],
                "sample.subpanel_id": subpanels,
                "sample.environment": list(ENVIRONMENT_OPTIONS),
                "asp.asp_group": groups,
            },
            **self.reviewer_options(),
        }

    def _validate_new_scope(self, payload: ClinicalRuleDraftCreate) -> None:
        """Check a draft scope against its active assay when lookup is configured.

        Args:
            payload: Draft request; an absent scope skips validation here.

        Raises:
            AppError: With status 409 for an absent/inactive assay or analyte mismatch.
        """
        if self.assay_panel_repository is None or payload.scope is None:
            return
        panel = self.assay_panel_repository.get_asp(payload.scope.asp_id)
        if not panel or panel.get("is_active") is False:
            raise api_error(409, "Clinical rule sets require an active assay panel")
        analyte = str(panel.get("asp_category") or "").lower()
        if analyte != payload.scope.analyte:
            raise api_error(409, "Clinical rule-set analyte does not match the assay panel")

    def _document(self, document_id: str) -> ClinicalRuleSetDoc:
        """Load and parse a stored rule version.

        Args:
            document_id: Repository identifier of the version.

        Returns:
            Validated canonical rule document.

        Raises:
            AppError: With status 404 when the version is absent.
            ValidationError: Stored data does not satisfy the canonical schema.
        """
        document = self.repository.get(document_id)
        if document is None:
            raise api_error(404, "Clinical rule-set version was not found")
        return ClinicalRuleSetDoc.model_validate(document)

    def _audit(self, action: str, document: ClinicalRuleSetDoc, actor: str) -> None:
        """Record a traceability event when an audit service is configured.

        Args:
            action: Lifecycle action appended to the clinical_rules event prefix.
            document: Version supplying resource, status, and assignment metadata.
            actor: Login responsible for the action.
        """
        if self.audit_service is None:
            return
        self.audit_service.record(
            f"clinical_rules.{action}",
            f"Clinical rule set {action}",
            category="clinical_reporting",
            actor=actor,
            resource_type="clinical_rule_set",
            resource_id=str(document.id_),
            resource_name=document.rule_set_id,
            tags=("clinical_rules", action),
            metadata={
                "rule_set_id": document.rule_set_id,
                "content_version": document.content_version,
                "revision": document.revision,
                "status": document.status.value,
                "clinical_reviewer": document.review.clinical_reviewer,
                "publisher": document.review.publisher,
            },
            retention_class="traceability",
        )

    def _eligible_users(self, permission: str) -> list[dict[str, str]]:
        """Return active accounts assigned a role with the requested capability."""
        if self.user_repository is None or self.role_repository is None:
            return []
        role_ids = [
            str(role.get("role_id") or "").strip()
            for role in self.role_repository.get_all_roles_plus_permissions()
            if permission in set(role.get("permissions") or [])
        ]
        if not role_ids:
            return []
        users = self.user_repository.list_active_users_for_notifications(role_ids=role_ids)
        return [
            {
                "username": str(user.get("username") or "").strip().lower(),
                "name": str(user.get("fullname") or user.get("username") or "").strip(),
            }
            for user in users
            if str(user.get("username") or "").strip()
        ]

    def reviewer_options(self) -> dict[str, list[dict[str, str]]]:
        """List active users eligible for clinical review and publication.

        Returns:
            Clinical reviewer and publisher choices; empty without identity repositories.
        """
        return {
            "clinical_reviewers": self._eligible_users("clinical_rules:clinical_review"),
            "publishers": self._eligible_users("clinical_rules:publish"),
        }

    def _validate_assignee(
        self, username: str | None, permission: str, *, label: str, exclude: str | None = None
    ) -> str:
        """Require an active assignee with the requested role capability.

        Args:
            username: Proposed login; None or blank is rejected.
            permission: Capability required through role membership.
            label: Assignee role label used in error messages.
            exclude: Optional login barred from assignment after normalization.

        Returns:
            Stripped, lowercase eligible login.

        Raises:
            AppError: With status 400 for no assignee or 409 for ineligibility/exclusion.
        """
        normalized = str(username or "").strip().lower()
        if not normalized:
            raise api_error(400, f"Assign an eligible {label} before continuing")
        eligible = {item["username"] for item in self._eligible_users(permission)}
        if normalized not in eligible:
            raise api_error(409, f"Assigned {label} is not an active eligible user")
        if normalized == str(exclude or "").strip().lower():
            raise api_error(409, f"The latest content editor cannot be the assigned {label}")
        return normalized

    def _notify(
        self, *, recipient: str, title: str, message: str, document: ClinicalRuleSetDoc, actor: str
    ) -> None:
        """Send a linked rule-workflow notification when a sender is configured.

        Args:
            recipient: Login receiving the notification.
            title: Notification heading.
            message: Workflow request or outcome text.
            document: Version linked from the notification.
            actor: Login recorded as notification creator.
        """
        if self.notification_service is None:
            return
        self.notification_service.create_notification(
            audience="users",
            recipients=[recipient],
            tone="info",
            category="clinical",
            title=title,
            message=message,
            source="Clinical reporting rules",
            created_by=actor,
            resource={
                "type": "clinical_rule_set",
                "id": str(document.id_),
                "name": document.name,
                "uri": f"/admin/clinical-rules?rule_set={document.id_}",
            },
        )

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
        return self._document(document_id).model_dump(mode="python", by_alias=True)

    def revisions(self, document_id: str) -> list[dict[str, Any]]:
        """Read revision history after confirming the version exists.

        Args:
            document_id: Version document identifier.

        Returns:
            Repository revision rows, or an empty list without revision storage.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        self._document(document_id)
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
        self._document(document_id)
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
        now = _now()
        if payload.source_version_id:
            source = self._document(payload.source_version_id)
            if source.status not in {ClinicalRuleStatus.PUBLISHED, ClinicalRuleStatus.REJECTED}:
                raise api_error(
                    409, "A draft can be cloned only from a published or rejected version"
                )
            document = source.model_dump(mode="python", by_alias=True)
            document.pop("_id", None)
            target_scope = payload.scope or source.scope
            self._validate_new_scope(
                ClinicalRuleDraftCreate(scope=target_scope, name=payload.name or source.name)
            )
            target_rule_set_id = (
                f"{target_scope.asp_id}__{target_scope.subpanel_id}__{target_scope.language}"
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
            self._validate_new_scope(payload)
            rule_set_id = (
                f"{payload.scope.asp_id}__{payload.scope.subpanel_id}__{payload.scope.language}"
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
                "minimum_engine_version": 1,
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
        self._audit("draft_created", saved, actor)
        return saved.model_dump(mode="python", by_alias=True)

    def import_draft(self, payload: ClinicalRuleImportRequest, *, actor: str) -> dict[str, Any]:
        """Validate a canonical export and create an independent editable draft."""
        try:
            source = ClinicalRuleSetDoc.model_validate(payload.document)
        except ValueError as exc:
            raise api_error(
                422, "Imported rule-set file is not a valid canonical export", str(exc)
            ) from exc
        create = ClinicalRuleDraftCreate(
            source_version_id=str(source.id_),
            scope=payload.scope,
            name=payload.name,
            source="api",
        )
        # Imported content is validated directly; it need not be persisted as a source version.
        now = _now()
        self._validate_new_scope(create)
        target_rule_set_id = (
            f"{payload.scope.asp_id}__{payload.scope.subpanel_id}__{payload.scope.language}"
        )
        document = source.model_dump(mode="python", by_alias=True)
        document.pop("_id", None)
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
                    "source_rule_set_id": source.rule_set_id,
                    "source_content_version": source.content_version,
                    "source_revision": source.revision,
                    "imported_schema_version": source.schema_version,
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
        self._audit("draft_imported", saved, actor)
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
        """
        changes = payload.model_dump(exclude={"revision"}, exclude_none=True, mode="python")
        changes.update({"updated_at": _now(), "updated_by": actor, "content_hash": None})
        candidate = self._document(document_id).model_copy(
            update={**deepcopy(changes), "revision": payload.revision + 1}
        )
        ClinicalRuleSetDoc.model_validate(candidate.model_dump(mode="python", by_alias=True))
        updated = self.repository.update_draft(
            document_id,
            expected_revision=payload.revision,
            changes=changes,
            actor=actor,
        )
        if updated is None:
            raise api_error(
                409,
                "The clinical rule draft changed while it was being edited",
                hint="Reload the draft and reconcile the newer revision before saving.",
            )
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        self._audit("draft_updated", parsed, actor)
        return parsed.model_dump(mode="python", by_alias=True)

    def delete_draft(self, document_id: str, *, expected_revision: int, actor: str) -> None:
        """Permanently discard an editable draft before clinical governance begins."""
        document = self._document(document_id)
        if document.status != ClinicalRuleStatus.DRAFT:
            raise api_error(409, "Only a draft clinical rule set can be deleted")
        deleted = self.repository.delete_draft(document_id, expected_revision=expected_revision)
        if deleted is None:
            raise api_error(
                409,
                "The clinical rule draft changed while it was being deleted. Reload and try again.",
            )
        self._audit("draft_deleted", document, actor)

    def validate(self, document_id: str) -> dict[str, Any]:
        """Validate a stored version's semantics and embedded cases.

        Args:
            document_id: Rule version identifier.

        Returns:
            Validity, errors, and warnings as Python values.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        return validate_rule_set(self._document(document_id)).model_dump(mode="python")

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
        document = self._document(document_id)
        context = PreparedReportContext.model_validate(facts)
        analyses = set(document.analysis_declarations)
        candidate = document.model_copy(update={"content_hash": content_hash(document)})
        return (
            ClinicalRuleEvaluator()
            .evaluate(context, candidate, reporting_analyses=analyses)
            .model_dump(mode="python")
        )

    def _transition(
        self,
        document_id: str,
        *,
        actor: str,
        reason: str,
        from_statuses: set[str],
        status: ClinicalRuleStatus,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Conditionally change lifecycle state, append its event, and audit it.

        Args:
            document_id: Version to transition.
            actor: Login recorded on the lifecycle and audit events.
            reason: Event explanation; blank is stored as None.
            from_statuses: Permitted current statuses passed to the repository.
            status: Target lifecycle state.
            extra: Optional additional update fields, including dotted review fields.

        Returns:
            Parsed and serialized updated version.

        Raises:
            AppError: With status 409 when the conditional transition is refused.
        """
        now = _now()
        changes = {"status": status.value, "updated_at": now, **(extra or {})}
        event = {
            "action": status.value,
            "actor": actor,
            "occurred_at": now,
            "reason": reason or None,
        }
        updated = self.repository.transition(
            document_id, from_statuses=from_statuses, changes=changes, event=event
        )
        if updated is None:
            raise api_error(409, f"Clinical rule set cannot transition to {status.value}")
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        self._audit(status.value, parsed, actor)
        return parsed.model_dump(mode="python", by_alias=True)

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
        """
        validation = validate_rule_set(self._document(document_id))
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        now = _now()
        reviewer = self._validate_assignee(
            payload.assignee,
            "clinical_rules:clinical_review",
            label="clinical reviewer",
            exclude=actor,
        )
        result = self._transition(
            document_id,
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
        self._notify(
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
            actor: Login that must equal the assigned clinical reviewer.

        Returns:
            Version in clinical review, after audit recording.

        Raises:
            AppError: With status 404 for a missing version or 409 for a different
                reviewer or refused lifecycle transition.
        """
        document = self._document(document_id)
        if document.review.clinical_reviewer != actor:
            raise api_error(409, "This clinical review is assigned to another user")
        result = self._transition(
            document_id,
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
            actor: Assigned reviewer login; the latest editor is rejected for either decision.

        Returns:
            Approved or rejected version with decision metadata.

        Raises:
            AppError: With status 404 for a missing version, 400 for no required
                publisher, or 409 for editor/reviewer, assignee, or state conflicts.

        Notes:
            Approval notifies the publisher; rejection notifies the draft creator.
        """
        document = self._document(document_id)
        if document.updated_by == actor:
            raise api_error(409, "The latest content editor cannot clinically approve this version")
        if document.review.clinical_reviewer != actor:
            raise api_error(409, "This clinical review is assigned to another user")
        publisher = None
        if payload.approve:
            publisher = self._validate_assignee(
                payload.publisher, "clinical_rules:publish", label="publisher"
            )
        status = ClinicalRuleStatus.APPROVED if payload.approve else ClinicalRuleStatus.REJECTED
        now = _now()
        result = self._transition(
            document_id,
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
        if payload.approve:
            approved = ClinicalRuleSetDoc.model_validate(result)
            self._notify(
                recipient=publisher,
                title="Clinical rule publication requested",
                message=f"{actor} clinically approved '{approved.name}' and assigned it for publication.",
                document=approved,
                actor=actor,
            )
        else:
            rejected = ClinicalRuleSetDoc.model_validate(result)
            self._notify(
                recipient=document.created_by,
                title="Clinical rule review rejected",
                message=f"{actor} rejected '{rejected.name}'. {payload.reason}",
                document=rejected,
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
        """
        document = self._document(document_id)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        if not document.review.clinical_reviewer:
            raise api_error(409, "Clinical approval is required before publication")
        if document.review.clinical_reviewer == document.updated_by:
            raise api_error(409, "Clinical approval must be independent of the latest editor")
        if document.review.publisher != actor:
            raise api_error(409, "This publication is assigned to another user")
        now = _now()
        digest = content_hash(document)
        event = {
            "action": "published",
            "actor": actor,
            "occurred_at": now,
            "reason": payload.reason or None,
        }
        updated = self.repository.publish(
            document_id,
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
        self._audit("published", parsed, actor)
        if parsed.created_by != actor:
            self._notify(
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
        now = _now()
        return self._transition(
            document_id,
            actor=actor,
            reason=payload.reason,
            from_statuses={"published"},
            status=ClinicalRuleStatus.RETIRED,
            extra={"active": False, "retired_at": now, "retired_by": actor},
        )
