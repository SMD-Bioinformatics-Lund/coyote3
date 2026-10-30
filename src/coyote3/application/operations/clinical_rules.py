"""Authenticated clinical-rule authoring with existing review and revision requirements."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from coyote3.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
    from coyote3.application.reporting.clinical_rules.testing import ClinicalRuleTestingService
    from coyote3.contracts.schemas.clinical_rules import (
        BulkAnnotationPreviewRequest,
        ClinicalRuleDecision,
        ClinicalRuleDraftCreate,
        ClinicalRuleDraftUpdate,
        ClinicalRuleImportRequest,
        ClinicalRuleReopenRequest,
        ClinicalRuleTransition,
    )


class ClinicalRules:
    """Inspect and govern reporting rules without bypassing assigned reviewers or publishers."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], ClinicalRuleAuthoringService],
        testing: Callable[[], ClinicalRuleTestingService],
    ) -> None:
        """Bind authenticated execution and the existing clinical-rule lifecycle service."""
        self._runtime, self._service = runtime, service
        self._testing = testing

    def facts(self) -> builtins.list[dict[str, Any]]:
        """List supported reporting facts under the clinical-rule view permission."""
        from coyote3.application.reporting.clinical_rules.registry import fact_catalog_payload

        return self._runtime.execute(
            "clinical_rules.facts",
            ("clinical_rules:view",),
            lambda actor, sample: fact_catalog_payload(),
        )

    def versions(self, rule_set_id: str) -> builtins.list[dict[str, Any]]:
        """Read retained versions of a logical rule set with current view access."""
        return self._runtime.execute(
            "clinical_rules.versions",
            ("clinical_rules:view",),
            lambda actor, sample: self._service().versions(rule_set_id),
        )

    def revisions(self, identity: str) -> builtins.list[dict[str, Any]]:
        """Read a version's verified revision history with current view access."""
        return self._runtime.execute(
            "clinical_rules.revisions",
            ("clinical_rules:view",),
            lambda actor, sample: self._service().revisions(identity),
        )

    def revision(self, identity: str, revision: int) -> dict[str, Any]:
        """Read one saved revision without changing the active reporting version."""
        return self._runtime.execute(
            "clinical_rules.revision",
            ("clinical_rules:view",),
            lambda actor, sample: self._service().revision(identity, revision),
        )

    def search_samples(
        self,
        document_id: str,
        *,
        search: str = "",
        match_diagnosis: bool = True,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Search ready samples within current grants and the authored rule scope.

        Args:
            document_id: Retained rule version whose scope defines candidate samples.
            search: Optional sample search text; empty omits text filtering.
            match_diagnosis: Restrict candidates to the rule diagnosis when True.
            page: One-based page number.
            per_page: Maximum samples per page, between 1 and 100.

        Returns:
            Existing candidate summaries after clinical_rules:test checks.
        """
        if page < 1 or not 1 <= per_page <= 100:
            raise ValueError("Page must be positive and page size must be between 1 and 100")
        return self._runtime.execute(
            "clinical_rules.search_samples",
            ("clinical_rules:test",),
            lambda actor, sample: self._testing().search_samples(
                document_id=document_id,
                search=search,
                match_diagnosis=match_diagnosis,
                allowed_asp_ids=None if actor.is_superuser else actor.asp_ids,
                allowed_environments=None if actor.is_superuser else actor.envs,
                page=page,
                per_page=per_page,
            ),
        )

    def preview_sample(
        self, document_id: str, sample_id: str, *, include_condition_trace: bool = False
    ) -> dict[str, Any]:
        """Evaluate a version on a freshly authorized sample without changing clinical state.

        Args:
            document_id: Retained authored version to evaluate.
            sample_id: Sample name or identifier whose current scope is checked.
            include_condition_trace: Include individual condition decisions when True.

        Returns:
            Existing sample-testing evaluation and report context.
        """
        from coyote3.application.operations.clinical import _sample

        return self._runtime.execute(
            "clinical_rules.preview_sample",
            ("clinical_rules:test",),
            lambda actor, sample: self._testing().preview(
                document_id=document_id,
                sample=_sample(sample),
                include_condition_trace=include_condition_trace,
            ),
            sample_id=sample_id,
        )

    def list(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """List retained rule versions with clinical_rules:view permission.

        Args:
            status: Lifecycle filter, or None for all statuses.
            search: Authoring search text, or None for no text filter.
            page: One-based page number.
            per_page: Page size between 1 and 200.

        Returns:
            Existing rule records with pagination and total count.
        """
        if page < 1 or not 1 <= per_page <= 200:
            raise ValueError("Page must be positive and page size must be between 1 and 200")
        return self._runtime.execute(
            "clinical_rules.list",
            ("clinical_rules:view",),
            lambda actor, sample: deepcopy(
                self._service().list(status=status, search=search, page=page, per_page=per_page)
            ),
        )

    def get(self, identity: str) -> dict[str, Any]:
        """Read one retained version with clinical_rules:view permission."""
        return self._runtime.execute(
            "clinical_rules.get",
            ("clinical_rules:view",),
            lambda actor, sample: deepcopy(self._service().get(identity)),
        )

    def export(self, identity: str, *, include_metadata: bool = False) -> dict[str, Any]:
        """Export rules under clinical_rules:view, omitting managed metadata by default.

        Args:
            identity: Version document identifier.
            include_metadata: Include stored lifecycle and audit metadata when True.

        Returns:
            Portable configuration or the full version when explicitly requested.
        """
        return self._runtime.execute(
            "clinical_rules.export",
            ("clinical_rules:view",),
            lambda actor, sample: self._service().export(
                identity, include_metadata=include_metadata
            ),
        )

    def options(self) -> dict[str, Any]:
        """Read registered authoring scopes with clinical_rules:view permission."""
        return self._runtime.execute(
            "clinical_rules.options",
            ("clinical_rules:view",),
            lambda actor, sample: deepcopy(self._service().authoring_options()),
        )

    def create(self, draft: ClinicalRuleDraftCreate) -> dict[str, Any]:
        """Create a validated draft attributed to the actor with clinical_rules:draft."""
        return self._runtime.execute(
            "clinical_rules.create",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().create_draft(draft, actor=actor.username)
            ),
        )

    def import_draft(self, request: ClinicalRuleImportRequest) -> dict[str, Any]:
        """Import a new attributed draft with clinical_rules:draft and existing validation."""
        return self._runtime.execute(
            "clinical_rules.import",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().import_draft(request, actor=actor.username)
            ),
        )

    def update(self, identity: str, update: ClinicalRuleDraftUpdate) -> dict[str, Any]:
        """Update a draft using the submitted expected revision and authenticated editor."""
        return self._runtime.execute(
            "clinical_rules.update",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().update_draft(identity, update, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
        )

    def delete_draft(self, identity: str, *, expected_revision: int) -> None:
        """Delete an unpublished draft under its revision guard with clinical_rules:draft."""
        self._runtime.execute(
            "clinical_rules.delete",
            ("clinical_rules:draft",),
            lambda actor, sample: self._service().delete_draft(
                identity, expected_revision=expected_revision, actor=actor.username
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def validate(self, identity: str) -> dict[str, Any]:
        """Validate authored rule content and cases with clinical_rules:draft permission."""
        return self._runtime.execute(
            "clinical_rules.validate",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(self._service().validate(identity)),
        )

    def preview_bulk_annotation(
        self, identity: str, facts: BulkAnnotationPreviewRequest
    ) -> dict[str, Any]:
        """Preview synthetic annotation wording under clinical-rule view access.

        Args:
            identity: Saved rule version identifier.
            facts: Finding values supplied without patient or sample identifiers.

        Returns:
            Matching template and text without writes.
        """
        return self._runtime.execute(
            "clinical_rules.preview_bulk_annotation",
            ("clinical_rules:view",),
            lambda actor, sample: self._service().preview_bulk_annotation(identity, facts),
        )

    def preview(self, identity: str, facts: dict[str, Any]) -> dict[str, Any]:
        """Evaluate supplied facts without loading sample records; requires clinical_rules:draft."""
        return self._runtime.execute(
            "clinical_rules.preview",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(self._service().preview(identity, facts)),
        )

    def reopen(self, identity: str, request: ClinicalRuleReopenRequest) -> dict[str, Any]:
        """Reopen an approved unpublished version under clinical_rules:draft access.

        Args:
            identity: Version to return to draft with its approval cleared.
            request: Expected revision and audit reason.

        Returns:
            Reopened version; published content cannot be reopened.
        """
        return self._runtime.execute(
            "clinical_rules.reopen",
            ("clinical_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().reopen_draft(identity, request, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def submit(self, identity: str, transition: ClinicalRuleTransition) -> dict[str, Any]:
        """Submit a revision for independent review with clinical_rules:submit."""
        return self._runtime.execute(
            "clinical_rules.submit",
            ("clinical_rules:submit",),
            lambda actor, sample: deepcopy(
                self._service().submit(identity, transition, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def start_review(self, identity: str, transition: ClinicalRuleTransition) -> dict[str, Any]:
        """Start the assigned clinical review with clinical_rules:clinical_review."""
        return self._runtime.execute(
            "clinical_rules.start_review",
            ("clinical_rules:clinical_review",),
            lambda actor, sample: deepcopy(
                self._service().start_review(identity, transition, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def decide(self, identity: str, decision: ClinicalRuleDecision) -> dict[str, Any]:
        """Record the assigned independent reviewer's decision and its publisher assignment."""
        return self._runtime.execute(
            "clinical_rules.decide",
            ("clinical_rules:clinical_review",),
            lambda actor, sample: deepcopy(
                self._service().clinical_decision(identity, decision, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def publish(self, identity: str, transition: ClinicalRuleTransition) -> dict[str, Any]:
        """Publish as the assigned publisher with clinical_rules:publish and revision guards."""
        return self._runtime.execute(
            "clinical_rules.publish",
            ("clinical_rules:publish",),
            lambda actor, sample: deepcopy(
                self._service().publish(identity, transition, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )

    def retire(self, identity: str, transition: ClinicalRuleTransition) -> dict[str, Any]:
        """Retire a publication with clinical_rules:retire, retaining its audit history."""
        return self._runtime.execute(
            "clinical_rules.retire",
            ("clinical_rules:retire",),
            lambda actor, sample: deepcopy(
                self._service().retire(identity, transition, actor=actor.username)
            ),
            edit_resource=("clinical-rules", identity),
            editing_session_required=False,
        )
