"""Permission-controlled configuration and query-policy authoring resources."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from coyote3.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote3.application.query_rules.service import QueryRuleService
    from coyote3.application.query_rules.testing import QueryRuleTestingService
    from coyote3.application.resources.configuration_profiles import ConfigurationProfileService
    from coyote3.application.resources.configuration_promotions import ConfigurationPromotionService
    from coyote3.contracts.configuration_profiles import (
        ConfigurationProfileDraft,
        ConfigurationPromotionRequest,
        ProfilePublication,
    )
    from coyote3.contracts.schemas.query_rules import (
        QueryConditionTest,
        QueryRuleDraft,
        QueryRulePreview,
        QueryRuleSampleSearch,
        QueryRuleTransition,
        QueryRuleUpdate,
    )


class ConfigurationProfiles:
    """Create and publish immutable source profiles under existing review rules."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ConfigurationProfileService]
    ) -> None:
        """Bind runtime authorization and the lazy configuration service."""
        self._runtime, self._service = runtime, service

    def list(self) -> list[dict[str, Any]]:
        """List profile revisions with assay.config:list permission."""
        return self._runtime.execute(
            "configuration_profiles.list",
            ("assay.config:list",),
            lambda actor, sample: deepcopy(self._service().list()),
        )

    def create(self, draft: ConfigurationProfileDraft) -> dict[str, Any]:
        """Save a validated draft attributed to the authenticated author.

        Args:
            draft: Immutable source content, scope bindings and review reason.

        Returns:
            The saved draft revision. Requires assay.config:create.
        """
        return self._runtime.execute(
            "configuration_profiles.create",
            ("assay.config:create",),
            lambda actor, sample: deepcopy(self._service().create(draft, actor=actor.username)),
        )

    def publish(self, identity: str, publication: ProfilePublication) -> dict[str, Any]:
        """Publish the exact reviewed content under the existing distinct-reviewer rule.

        Args:
            identity: Retained profile revision identifier.
            publication: Reviewed content hash and reason; stale hashes are rejected.

        Returns:
            Published revision. Requires configuration:publish.
        """
        return self._runtime.execute(
            "configuration_profiles.publish",
            ("configuration:publish",),
            lambda actor, sample: deepcopy(
                self._service().publish(
                    identity,
                    actor=actor.username,
                    content_hash=publication.content_hash,
                    reason=publication.reason,
                )
            ),
        )


class ConfigurationPromotions:
    """Propose and approve reviewed releases without rebinding existing samples."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ConfigurationPromotionService]
    ) -> None:
        """Bind runtime authorization and the lazy promotion service."""
        self._runtime, self._service = runtime, service

    def list(self) -> list[dict[str, Any]]:
        """List proposals with assay.config:list permission."""
        return self._runtime.execute(
            "configuration_promotions.list",
            ("assay.config:list",),
            lambda actor, sample: deepcopy(self._service().list()),
        )

    def propose(self, request: ConfigurationPromotionRequest) -> dict[str, Any]:
        """Propose a source revision for another environment with validation evidence."""
        return self._runtime.execute(
            "configuration_promotions.propose",
            ("assay.config:create",),
            lambda actor, sample: deepcopy(self._service().propose(request, actor=actor.username)),
        )

    def approve(self, identity: str, publication: ProfilePublication) -> dict[str, Any]:
        """Approve the reviewed hash as a distinct reviewer with configuration:publish."""
        return self._runtime.execute(
            "configuration_promotions.approve",
            ("configuration:publish",),
            lambda actor, sample: deepcopy(
                self._service().approve(
                    identity,
                    actor=actor.username,
                    content_hash=publication.content_hash,
                    reason=publication.reason,
                )
            ),
        )


class QueryRules:
    """Author, inspect and transition query policies through existing version checks."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], QueryRuleService],
        testing: Callable[[], QueryRuleTestingService],
    ) -> None:
        """Bind the execution boundary and current query-policy service."""
        self._runtime, self._service = runtime, service
        self._testing = testing

    def search_samples(self, request: QueryRuleSampleSearch) -> dict[str, Any]:
        """Search ready policy-testing samples using current actor scope assignments.

        Args:
            request: Authoring scope, search text and one-based page number.

        Returns:
            Existing ready sample summaries and pagination within the actor's grants.
        """
        return self._runtime.execute(
            "query_rules.search_samples",
            ("query_rules:test",),
            lambda actor, sample: self._testing().search_samples(
                scope=request.scope,
                search=request.search,
                page=request.page,
                allowed_asp_ids=None if actor.is_superuser else actor.asp_ids,
                allowed_environments=None if actor.is_superuser else actor.envs,
            ),
        )

    def preview_sample(self, sample_id: str, request: QueryRulePreview) -> dict[str, Any]:
        """Compare current and proposed selections after current sample authorization.

        Args:
            sample_id: Sample name or identifier to reload and authorize.
            request: Proposed policy scope and optional draft content.

        Returns:
            Existing read-only selection comparison and diagnostics.
        """
        from coyote3.application.operations.clinical import _sample

        return self._runtime.execute(
            "query_rules.preview_sample",
            ("query_rules:test",),
            lambda actor, sample: self._testing().preview(
                request,
                _sample(sample),
                allowed_asp_ids=None if actor.is_superuser else actor.asp_ids,
                allowed_environments=None if actor.is_superuser else actor.envs,
            ),
            sample_id=sample_id,
        )

    def list(self) -> dict[str, Any]:
        """List retained policies with query_rules:view permission."""
        return self._runtime.execute(
            "query_rules.list",
            ("query_rules:view",),
            lambda actor, sample: deepcopy(self._service().list()),
        )

    def options(self) -> dict[str, Any]:
        """Return registered authoring scopes with query_rules:view permission."""
        return self._runtime.execute(
            "query_rules.options",
            ("query_rules:view",),
            lambda actor, sample: deepcopy(self._service().options()),
        )

    def preview(self, request: QueryRulePreview) -> dict[str, Any]:
        """Resolve published and proposed policy content after validating the authored scope."""

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Preserve scope validation before resolving candidate policy content."""
            service = self._service()
            service.validate_scope(request.scope)
            return deepcopy(service.resolve(request.scope, request.content))

        return self._runtime.execute("query_rules.preview", ("query_rules:view",), read)

    def test_condition(self, request: QueryConditionTest) -> dict[str, Any]:
        """Evaluate a condition on supplied synthetic records without querying samples."""
        return self._runtime.execute(
            "query_rules.test_condition",
            ("query_rules:view",),
            lambda actor, sample: deepcopy(self._service().test_condition(request)),
        )

    def create(self, draft: QueryRuleDraft) -> dict[str, Any]:
        """Create a policy draft attributed to the current author with query_rules:draft."""
        return self._runtime.execute(
            "query_rules.create",
            ("query_rules:draft",),
            lambda actor, sample: deepcopy(self._service().create(draft, actor.username)),
        )

    def update(self, identity: str, update: QueryRuleUpdate) -> dict[str, Any]:
        """Update a draft using its expected revision and current authenticated author."""
        return self._runtime.execute(
            "query_rules.update",
            ("query_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().update(identity, update, actor.username)
            ),
            edit_resource=("query-rules", identity),
        )

    def revisions(self, identity: str) -> builtins.list[dict[str, Any]]:
        """Read verified immutable policy history with query_rules:view permission."""
        return self._runtime.execute(
            "query_rules.revisions",
            ("query_rules:view",),
            lambda actor, sample: deepcopy(self._service().revisions(identity)),
        )

    def publish(self, identity: str, transition: QueryRuleTransition) -> dict[str, Any]:
        """Publish an approved revision atomically with query_rules:publish permission."""
        return self._runtime.execute(
            "query_rules.publish",
            ("query_rules:publish",),
            lambda actor, sample: deepcopy(
                self._service().transition(identity, "publish", transition, actor.username)
            ),
            edit_resource=("query-rules", identity),
            editing_session_required=False,
        )

    def approve(self, identity: str, transition: QueryRuleTransition) -> dict[str, Any]:
        """Approve another author's draft with query_rules:review and revision validation."""
        return self._runtime.execute(
            "query_rules.approve",
            ("query_rules:review",),
            lambda actor, sample: deepcopy(
                self._service().transition(identity, "approve", transition, actor.username)
            ),
            edit_resource=("query-rules", identity),
            editing_session_required=False,
        )

    def retire(self, identity: str, transition: QueryRuleTransition) -> dict[str, Any]:
        """Retire a revision with query_rules:retire, retaining its immutable history."""
        return self._runtime.execute(
            "query_rules.retire",
            ("query_rules:retire",),
            lambda actor, sample: deepcopy(
                self._service().transition(identity, "retire", transition, actor.username)
            ),
            edit_resource=("query-rules", identity),
            editing_session_required=False,
        )

    def delete_draft(self, identity: str, transition: QueryRuleTransition) -> dict[str, Any]:
        """Delete an unpublished revision with query_rules:draft and revision validation."""
        return self._runtime.execute(
            "query_rules.delete_draft",
            ("query_rules:draft",),
            lambda actor, sample: deepcopy(
                self._service().delete_draft(identity, transition, actor.username)
            ),
            edit_resource=("query-rules", identity),
            editing_session_required=False,
        )
