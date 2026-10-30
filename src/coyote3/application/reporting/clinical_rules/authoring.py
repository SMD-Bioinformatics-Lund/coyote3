"""Governed authoring and publication workflows for clinical rule sets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from coyote3.application.classification.bulk_annotation_rules import render_bulk_annotation
from coyote3.application.common.protected_records import reject_system_managed_change
from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.facts import PreparedReportContext
from coyote3.application.reporting.clinical_rules.registry import BULK_ANNOTATION_FACT_PATHS
from coyote3.application.reporting.clinical_rules.validation import (
    content_hash,
    validate_rule_set,
)
from coyote3.application.resources.availability import require_active_group
from coyote3.config.constants import DIAGNOSIS_BASE_ID, ENVIRONMENT_OPTIONS
from coyote3.contracts.schemas.clinical_rules import (
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
from coyote3.domain.common.errors import api_error
from coyote3.domain.common.reporting import (
    STANDARD_CNV_SUMMARY_PHRASES,
    STANDARD_TIER_SUMMARY_PHRASES,
)
from coyote3.domain.common.resource_names import short_resource_name


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
    def from_store(cls, store: Any) -> "ClinicalRuleAuthoringService":
        """Bind authoring to rule, revision, assay, and optional identity repositories.

        Args:
            store: Repository provider; user and role repositories may be absent.

        Returns:
            Authoring service without a notification service configured.
        """
        return cls(
            store.clinical_rule_set_repository,
            revision_repository=store.clinical_rule_revision_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_diagnosis_repository=store.assay_diagnosis_repository,
            assay_setup_repository=getattr(store, "assay_setup_repository", None),
            user_repository=getattr(store, "user_repository", None),
            role_repository=getattr(store, "roles_repository", None),
        )

    def __init__(
        self,
        repository: Any,
        *,
        revision_repository: Any | None = None,
        assay_panel_repository: Any | None = None,
        assay_diagnosis_repository: Any | None = None,
        assay_setup_repository: Any | None = None,
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
            assay_setup_repository: Unpublished setup scopes available only to rule authoring.
            user_repository: Optional active-user lookup for assignments.
            role_repository: Optional permission-to-role lookup for assignments.
            notification_service: Optional sender of review and publication requests.
        """
        self.repository = repository
        self.revision_repository = revision_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_diagnosis_repository = assay_diagnosis_repository
        self.assay_setup_repository = assay_setup_repository
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.notification_service = notification_service

    def authoring_options(self) -> dict[str, Any]:
        """Return authoring scopes and optional sentence wording for explicit draft insertion."""
        sentence_terminology = {
            "sv": {
                "tier_summary": {
                    **deepcopy(STANDARD_TIER_SUMMARY_PHRASES),
                    "single_gene_always_read_context": True,
                },
                "cnv_summary": deepcopy(STANDARD_CNV_SUMMARY_PHRASES),
            }
        }
        if self.assay_panel_repository is None:
            return {
                "assays": [],
                "condition_values": {},
                "sentence_terminology": sentence_terminology,
                "bulk_annotation_fact_paths": sorted(BULK_ANNOTATION_FACT_PATHS),
                **self.reviewer_options(),
            }
        assays = []
        for panel in self._authoring_panels():
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
                    "name": short_resource_name(panel, asp_id),
                    "analyte": analyte,
                    "diagnoses": [
                        {
                            "diagnosis_id": scope["diagnosis_id"],
                            "display_name": scope["display_name"],
                        }
                        for scope in self._registered_diagnoses(asp_id)
                    ],
                }
            )
        diagnoses = sorted(
            {scope["diagnosis_id"] for assay in assays for scope in assay["diagnoses"]}
        )
        groups = sorted(
            {str(panel.get("asp_group") or "").strip() for panel in self._authoring_panels()} - {""}
        )
        return {
            "sentence_terminology": sentence_terminology,
            "bulk_annotation_fact_paths": sorted(BULK_ANNOTATION_FACT_PATHS),
            "assays": sorted(assays, key=lambda item: (item["display_name"], item["asp_id"])),
            "condition_values": {
                "sample.asp_id": [item["asp_id"] for item in assays],
                "sample.diagnosis_id": diagnoses,
                "sample.environment": list(ENVIRONMENT_OPTIONS),
                "asp.asp_group": groups,
            },
            **self.reviewer_options(),
        }

    def _authoring_panels(self) -> list[dict[str, Any]]:
        """Combine active assays with reserved setup drafts, without changing runtime lookup."""
        panels = list(self.assay_panel_repository.get_all_asps(is_active=True))
        if self.assay_setup_repository is not None:
            for setup in self.assay_setup_repository.authoring_scopes():
                panel = setup["content"]["panel"]
                if not self.assay_panel_repository.get_asp(panel["asp_id"]):
                    panels.append({**panel, "is_active": True})
        return panels

    def _registered_diagnoses(self, asp_id: str) -> list[dict[str, Any]]:
        """Return active registered scopes; fail closed when the repository is not configured."""
        if self.assay_diagnosis_repository is None:
            raise RuntimeError("Assay diagnosis repository is required for rule authoring")
        if self.assay_setup_repository is not None and not self.assay_panel_repository.get_asp(
            asp_id
        ):
            for setup in self.assay_setup_repository.authoring_scopes():
                if setup["content"]["panel"]["asp_id"] == asp_id:
                    definitions = self.assay_diagnosis_repository.list_definitions()
                    return [{"diagnosis_id": DIAGNOSIS_BASE_ID, "display_name": "Base"}] + [
                        d
                        for d in definitions
                        if d["diagnosis_id"] in setup["content"]["scopes"] and d["is_active"]
                    ]
        return [{"diagnosis_id": DIAGNOSIS_BASE_ID, "display_name": "Base"}] + [
            row
            for row in self.assay_diagnosis_repository.list_for_assay(asp_id, active_only=True)
            if row["diagnosis_id"] != DIAGNOSIS_BASE_ID
        ]

    def _validate_new_scope(
        self, payload: ClinicalRuleDraftCreate, *, allow_unregistered: bool = False
    ) -> None:
        """Check assay compatibility, optionally accepting a planned assay for authoring.

        Args:
            payload: Draft request; an absent scope skips validation here.
            allow_unregistered: Permit a missing assay while authoring a draft;
                existing inactive or incompatible assays are still rejected.

        Raises:
            AppError: With status 409 for an unavailable assay/setup or analyte mismatch.
        """
        if self.assay_panel_repository is None or payload.scope is None:
            return
        panel = self.assay_panel_repository.get_asp(payload.scope.asp_id)
        if panel is None and self.assay_setup_repository is not None:
            panel = next(
                (p for p in self._authoring_panels() if p["asp_id"] == payload.scope.asp_id), None
            )
        if panel is None and allow_unregistered:
            return
        if not panel or panel.get("is_active") is False:
            raise api_error(409, "Clinical rule sets require an active assay panel")
        analyte = str(panel.get("asp_category") or "").lower()
        if analyte != payload.scope.analyte:
            raise api_error(409, "Clinical rule-set analyte does not match the assay panel")
        if payload.scope.diagnosis_id not in {
            scope["diagnosis_id"] for scope in self._registered_diagnoses(payload.scope.asp_id)
        }:
            raise api_error(409, "Select an active registered diagnosis for this assay")

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
            category="application",
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
        document = self._document(document_id)
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
            self._validate_new_scope(payload, allow_unregistered=True)
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
        create = ClinicalRuleDraftCreate(
            scope=payload.scope,
            name=payload.name,
            source="api",
        )
        # Imported content is validated directly; it need not be persisted as a source version.
        now = _now()
        self._validate_new_scope(create, allow_unregistered=True)
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
                    "source_rule_set_id": (
                        f"{source.scope.asp_id}__{source.scope.diagnosis_id}__{source.scope.language}"
                    ),
                    "imported_schema_version": source.schema_version,
                    **{
                        f"source_{key}": value
                        for key in ("content_version", "revision")
                        if isinstance(value := payload.document.get(key), int)
                        and not isinstance(value, bool)
                        and value > 0
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
        changes.update({"updated_at": _now(), "updated_by": actor, "content_hash": None})
        current = self._document(document_id)
        candidate = current.model_dump(mode="python", by_alias=True)
        reject_system_managed_change(candidate, resource="reporting rule")
        if payload.scope is not None:
            if current.status != ClinicalRuleStatus.DRAFT:
                raise api_error(409, "Only a draft can change its assay association")
            self._validate_new_scope(ClinicalRuleDraftCreate(scope=payload.scope))
            target_id = (
                f"{payload.scope.asp_id}__{payload.scope.diagnosis_id}__{payload.scope.language}"
            )
            changes["rule_set_id"] = target_id
            if target_id != current.rule_set_id:
                changes["content_version"] = self.repository.next_content_version(target_id)
        candidate.update({**deepcopy(changes), "revision": payload.revision + 1})
        ClinicalRuleSetDoc.model_validate(candidate)
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
        return parsed.model_dump(mode="python", by_alias=True)

    def delete_draft(self, document_id: str, *, expected_revision: int, actor: str) -> None:
        """Discard a pre-publication version while preserving released versions and audit."""
        document = self._document(document_id)
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
        return validate_rule_set(self._document(document_id)).model_dump(mode="python")

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
        document = self._document(document_id)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise api_error(422, "Clinical rule validation failed", "; ".join(validation.errors))
        try:
            return render_bulk_annotation(document, facts).model_dump(mode="python")
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
        expected_revision: int,
        actor: str,
        reason: str,
        from_statuses: set[str],
        status: ClinicalRuleStatus,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Conditionally change lifecycle state, append its event, and audit it.

        Args:
            document_id: Version to transition.
            expected_revision: Revision read during validation and authorization.
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
        stored = self.repository.get(document_id)
        if stored is None:
            raise api_error(404, "Clinical rule-set version was not found")
        reject_system_managed_change(stored, resource="reporting rule")
        changes = {"status": status.value, "updated_at": now, **(extra or {})}
        event = {
            "action": status.value,
            "actor": actor,
            "occurred_at": now,
            "reason": reason or None,
        }
        updated = self.repository.transition(
            document_id,
            expected_revision=expected_revision,
            from_statuses=from_statuses,
            changes=changes,
            event=event,
        )
        if updated is None:
            raise api_error(409, f"Clinical rule set cannot transition to {status.value}")
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        return parsed.model_dump(mode="python", by_alias=True)

    def reopen_draft(
        self, document_id: str, payload: ClinicalRuleReopenRequest, *, actor: str
    ) -> dict[str, Any]:
        """Return an approved unpublished version to draft and revoke its approval.

        Args:
            document_id: Approved version to reopen without changing its identity.
            payload: Revision seen by the editor and an audit reason.
            actor: Authorized editor recorded as the latest editor.

        Returns:
            Same content version at its next revision, with review metadata cleared.

        Raises:
            AppError: Version is absent, protected, stale or no longer approved.

        Notes:
            Previous approval remains in immutable revision/lifecycle history.
            The revision and approved-state predicate fence concurrent publication.
        """
        document = self._document(document_id)
        if document.status != ClinicalRuleStatus.APPROVED:
            raise api_error(409, "Only an approved unpublished version can be reopened")
        if document.revision != payload.revision:
            raise api_error(409, "The approved rule set changed. Reload before editing again.")
        return self._transition(
            document_id,
            expected_revision=payload.revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"approved"},
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
        document = self._document(document_id)
        self._validate_new_scope(ClinicalRuleDraftCreate(scope=document.scope))
        validation = validate_rule_set(document)
        reject_system_managed_change(document.model_dump(), resource="clinical rule set")
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
            Requires valid rule semantics and an unchanged validated revision.
            Embedded cases are not required or executed.
        """
        document = self._document(document_id)
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
            (p for p in self._authoring_panels() if p["asp_id"] == document.scope.asp_id), None
        )
        if panel is None:
            raise api_error(409, "Assay is unavailable for publication")
        require_active_group(self.assay_panel_repository, panel["asp_group"])
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
            expected_revision=self._document(document_id).revision,
            actor=actor,
            reason=payload.reason,
            from_statuses={"published"},
            status=ClinicalRuleStatus.RETIRED,
            extra={"active": False, "retired_at": now, "retired_by": actor},
        )
