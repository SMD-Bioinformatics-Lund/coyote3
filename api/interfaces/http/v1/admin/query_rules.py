"""Permission-controlled query-policy authoring, preview and lifecycle routes."""

from fastapi import APIRouter, Depends

from api.app.deps.application import get_query_rules
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access
from coyote3.application.operations import QueryRules
from coyote3.contracts.schemas.query_rules import (
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

router = APIRouter(prefix="/api/v1/admin/query-rule-sets", tags=[TAG_ADMIN_ASSAYS])


@router.post("/test-samples", response_model=QueryRuleSampleSearchResult)
def search_test_samples(
    payload: QueryRuleSampleSearch,
    user: ApiUser = Depends(require_access(permission="query_rules:test")),
    service: QueryRules = Depends(get_query_rules),
):
    """Search ready samples within assay and environment grants; requires query_rules:test."""
    return service.search_samples(payload)


@router.post("/test-samples/{sample_id}/preview", response_model=QueryRuleSampleResult)
def preview_sample(
    sample_id: str,
    payload: QueryRulePreview,
    user: ApiUser = Depends(require_access(permission="query_rules:test")),
    service: QueryRules = Depends(get_query_rules),
):
    """Compare published and proposed query selections without writes; requires query_rules:test."""
    return service.preview_sample(sample_id, payload)


@router.post("/test-condition", response_model=QueryConditionTestResult)
def test_condition(
    payload: QueryConditionTest,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRules = Depends(get_query_rules),
):
    """Test a condition against supplied synthetic records; requires query_rules:view.

    Does not retrieve sample data, execute MongoDB queries or persist test records.
    """
    return service.test_condition(payload)


@router.get("/options", response_model=QueryRuleOptions)
def rule_options(
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRules = Depends(get_query_rules),
):
    """List registered authoring scopes; requires query_rules:view."""
    return service.options()


@router.get("", response_model=QueryRuleList)
def list_rules(
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRules = Depends(get_query_rules),
):
    """List policy versions; requires query_rules:view."""
    return service.list()


@router.post("/preview", response_model=QueryRuleResolution)
def preview_rules(
    payload: QueryRulePreview,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRules = Depends(get_query_rules),
):
    """Preview effective published policy and optional draft fields without writes."""
    return service.preview(payload)


@router.post("", response_model=QueryRuleDoc, status_code=201)
def create_rule(
    payload: QueryRuleDraft,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRules = Depends(get_query_rules),
):
    """Create a draft version; requires query_rules:draft."""
    return service.create(payload)


@router.put("/{identifier}", response_model=QueryRuleDoc)
def update_rule(
    identifier: str,
    payload: QueryRuleUpdate,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRules = Depends(get_query_rules),
):
    """Update an inspected draft revision; published versions are immutable."""
    return service.update(identifier, payload)


@router.post("/{identifier}/approve", response_model=QueryRuleDoc)
def approve_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:review")),
    service: QueryRules = Depends(get_query_rules),
):
    """Approve a draft authored by another user; requires query_rules:review."""
    return service.approve(identifier, payload)


@router.delete("/{identifier}", response_model=QueryRuleDoc)
def delete_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:draft")),
    service: QueryRules = Depends(get_query_rules),
):
    """Delete an unpublished version and private snapshots; requires query_rules:draft."""
    return service.delete_draft(identifier, payload)


@router.get("/{identifier}/revisions", response_model=list[QueryRuleRevisionDoc])
def rule_revisions(
    identifier: str,
    user: ApiUser = Depends(require_access(permission="query_rules:view")),
    service: QueryRules = Depends(get_query_rules),
):
    """Read verified immutable query-rule history; requires query_rules:view."""
    return service.revisions(identifier)


@router.post("/{identifier}/publish", response_model=QueryRuleDoc)
def publish_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:publish")),
    service: QueryRules = Depends(get_query_rules),
):
    """Publish an approved version atomically; requires query_rules:publish."""
    return service.publish(identifier, payload)


@router.post("/{identifier}/retire", response_model=QueryRuleDoc)
def retire_rule(
    identifier: str,
    payload: QueryRuleTransition,
    user: ApiUser = Depends(require_access(permission="query_rules:retire")),
    service: QueryRules = Depends(get_query_rules),
):
    """Retire a publication to restore parent inheritance; requires query_rules:retire."""
    return service.retire(identifier, payload)
