"""Governed authoring and publication workflows for clinical rule sets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
    ClinicalRuleTransition,
)
from api.domain.common.errors import api_error


def _now() -> datetime:
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
        return cls(
            store.clinical_rule_set_repository,
            revision_repository=store.clinical_rule_revision_repository,
            audit_service=audit_service,
            assay_panel_repository=store.assay_panel_repository,
        )

    def __init__(
        self,
        repository: Any,
        *,
        revision_repository: Any | None = None,
        audit_service: Any | None = None,
        assay_panel_repository: Any | None = None,
    ) -> None:
        self.repository = repository
        self.revision_repository = revision_repository
        self.audit_service = audit_service
        self.assay_panel_repository = assay_panel_repository

    def authoring_options(self) -> dict[str, list[dict[str, str]]]:
        """Return active assay scopes available for new rule sets."""
        if self.assay_panel_repository is None:
            return {"assays": []}
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
        return {"assays": sorted(assays, key=lambda item: (item["display_name"], item["asp_id"]))}

    def _validate_new_scope(self, payload: ClinicalRuleDraftCreate) -> None:
        if self.assay_panel_repository is None or payload.scope is None:
            return
        panel = self.assay_panel_repository.get_asp(payload.scope.asp_id)
        if not panel or panel.get("is_active") is False:
            raise api_error(409, "Clinical rule sets require an active assay panel")
        analyte = str(panel.get("asp_category") or "").lower()
        if analyte != payload.scope.analyte:
            raise api_error(409, "Clinical rule-set analyte does not match the assay panel")

    def _document(self, document_id: str) -> ClinicalRuleSetDoc:
        document = self.repository.get(document_id)
        if document is None:
            raise api_error(404, "Clinical rule-set version was not found")
        return ClinicalRuleSetDoc.model_validate(document)

    def _audit(self, action: str, document: ClinicalRuleSetDoc, actor: str) -> None:
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
            },
            retention_class="traceability",
        )

    def list(
        self, *, status: str | None, search: str | None, page: int, per_page: int
    ) -> dict[str, Any]:
        skip = (page - 1) * per_page
        rows, total = self.repository.list_rule_sets(
            status=status, search=search, skip=skip, limit=per_page
        )
        return {"items": rows, "page": page, "per_page": per_page, "total": total}

    def versions(self, rule_set_id: str) -> list[dict[str, Any]]:
        return self.repository.list_versions(rule_set_id)

    def get(self, document_id: str) -> dict[str, Any]:
        return self._document(document_id).model_dump(mode="python", by_alias=True)

    def revisions(self, document_id: str) -> list[dict[str, Any]]:
        self._document(document_id)
        if self.revision_repository is None:
            return []
        return self.revision_repository.list_for_version(document_id)

    def revision(self, document_id: str, revision: int) -> dict[str, Any]:
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
        now = _now()
        if payload.source_version_id:
            source = self._document(payload.source_version_id)
            if source.status not in {ClinicalRuleStatus.PUBLISHED, ClinicalRuleStatus.REJECTED}:
                raise api_error(
                    409, "A draft can be cloned only from a published or rejected version"
                )
            document = source.model_dump(mode="python", by_alias=True)
            document.pop("_id", None)
            document.update(
                {
                    "content_version": self.repository.next_content_version(source.rule_set_id),
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

    def update_draft(
        self, document_id: str, payload: ClinicalRuleDraftUpdate, *, actor: str
    ) -> dict[str, Any]:
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
        return validate_rule_set(self._document(document_id)).model_dump(mode="python")

    def preview(self, document_id: str, facts: dict[str, Any]) -> dict[str, Any]:
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
        validation = validate_rule_set(self._document(document_id))
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        now = _now()
        return self._transition(
            document_id,
            actor=actor,
            reason=payload.reason,
            from_statuses={"draft"},
            status=ClinicalRuleStatus.SUBMITTED,
            extra={"review.submitted_by": actor, "review.submitted_at": now},
        )

    def start_review(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        return self._transition(
            document_id,
            actor=actor,
            reason=payload.reason,
            from_statuses={"submitted"},
            status=ClinicalRuleStatus.IN_CLINICAL_REVIEW,
            extra={"review.clinical_reviewer": actor},
        )

    def clinical_decision(
        self, document_id: str, payload: ClinicalRuleDecision, *, actor: str
    ) -> dict[str, Any]:
        document = self._document(document_id)
        if document.updated_by == actor:
            raise api_error(409, "The latest content editor cannot clinically approve this version")
        status = ClinicalRuleStatus.APPROVED if payload.approve else ClinicalRuleStatus.REJECTED
        now = _now()
        return self._transition(
            document_id,
            actor=actor,
            reason=payload.reason,
            from_statuses={"in_clinical_review"},
            status=status,
            extra={
                "review.clinical_reviewer": actor,
                "review.clinical_decision_at": now,
                "review.clinical_decision_reason": payload.reason,
            },
        )

    def publish(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
        document = self._document(document_id)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        if not document.review.clinical_reviewer:
            raise api_error(409, "Clinical approval is required before publication")
        if document.review.clinical_reviewer == document.updated_by:
            raise api_error(409, "Clinical approval must be independent of the latest editor")
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
        return parsed.model_dump(mode="python", by_alias=True)

    def retire(
        self, document_id: str, payload: ClinicalRuleTransition, *, actor: str
    ) -> dict[str, Any]:
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
