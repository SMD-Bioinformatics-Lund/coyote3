"""Permission-controlled query-policy authoring, preview and lifecycle routes."""

from fastapi import APIRouter, Depends

from api.app.deps.services import get_query_rule_service, get_query_rule_testing_service
from api.application.query_rule_testing import QueryRuleTestingService
from api.application.query_rules import QueryRuleService
from api.contracts.schemas.query_rules import (
    QueryConditionTest,
    QueryConditionTestResult,
    QueryRuleDoc,
    QueryRuleDraft,
    QueryRuleList,
    QueryRuleOptions,
    QueryRulePreview,
    QueryRuleResolution,
    QueryRuleRevisionDoc,
    QueryRuleSampleResult,
    QueryRuleSampleSearch,
    QueryRuleSampleSearchResult,
    QueryRuleTransition,
    QueryRuleUpdate,
)
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(prefix="/api/v1/admin/query-rule-sets", tags=[TAG_ADMIN_ASSAYS])


@router.post("/test-samples", response_model=QueryRuleSampleSearchResult)
def search_test_samples(
    payload: QueryRuleSampleSearch,
    user: ApiUser = Depends(require_access(permission="query_rules:test")),
    service: QueryRuleTestingService = Depends(get_query_rule_testing_service),
):
    """Search ready samples within assay and environment grants; requires query_rules:test."""
    return service.search_samples(
        scope=payload.scope,
        search=payload.search,
        page=payload.page,
        allowed_asp_ids=None if user.is_superuser else user.asp_ids,
        allowed_environments=None if user.is_superuser else user.envs,
    )


@router.post("/test-samples/{sample_id}/preview", response_model=QueryRuleSampleResult)
def preview_sample(
    sample_id: str,
    payload: QueryRulePreview,
    user: ApiUser = Depends(require_access(permission="query_rules:test")),
    service: QueryRuleTestingService = Depends(get_query_rule_testing_service),
):
    """Compare published and proposed query selections without writes; requires query_rules:test."""
    sample = _get_sample_for_api(sample_id, user)
    return service.preview(
        payload,
        sample,
        allowed_asp_ids=None if user.is_superuser else user.asp_ids,
        allowed_environments=None if user.is_superuser else user.envs,
    )


@router.post("/test-condition", response_model=QueryConditionTestResult)
def test_condition(
    payload: QueryConditionTest,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Test a condition against supplied synthetic records; requires query_rules:view.

    Does not retrieve sample data, execute MongoDB queries or persist test records.
    """
    return service.test_condition(payload)


@router.get("/options", response_model=QueryRuleOptions)
def rule_options(
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """List registered authoring scopes; requires query_rules:view."""
    return service.options()


@router.get("", response_model=QueryRuleList)
def list_rules(
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """List policy versions; requires query_rules:view."""
    return service.list()


@router.post("/preview", response_model=QueryRuleResolution)
def preview_rules(
    payload: QueryRulePreview,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Preview effective published policy and optional draft fields without writes."""
    service.validate_scope(payload.scope)
    return service.resolve(payload.scope, payload.content)


@router.post("", response_model=QueryRuleDoc, status_code=201)
def create_rule(
    payload: QueryRuleDraft,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Create a draft version; requires query_rules:draft."""
    return service.create(payload, user.username)


@router.put("/{identifier}", response_model=QueryRuleDoc)
def update_rule(
    identifier: str,
    payload: QueryRuleUpdate,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Update an inspected draft revision; published versions are immutable."""
    return service.update(identifier, payload, user.username)


@router.post("/{identifier}/approve", response_model=QueryRuleDoc)
def approve_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:review")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Approve a draft authored by another user; requires query_rules:review."""
    return service.transition(identifier, "approve", payload, user.username)


@router.delete("/{identifier}", response_model=QueryRuleDoc)
def delete_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Delete an unchanged draft and private snapshots; requires query_rules:draft."""
    return service.delete_draft(identifier, payload, user.username)


@router.get("/{identifier}/revisions", response_model=list[QueryRuleRevisionDoc])
def rule_revisions(
    identifier: str,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Read verified immutable query-rule history; requires query_rules:view."""
    return service.revisions(identifier)


@router.post("/{identifier}/publish", response_model=QueryRuleDoc)
def publish_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:publish")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Publish an approved version atomically; requires query_rules:publish."""
    return service.transition(identifier, "publish", payload, user.username)


@router.post("/{identifier}/retire", response_model=QueryRuleDoc)
def retire_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:retire")),
    service: QueryRuleService = Depends(get_query_rule_service),
):
    """Retire a publication to restore parent inheritance; requires query_rules:retire."""
    return service.transition(identifier, "retire", payload, user.username)
