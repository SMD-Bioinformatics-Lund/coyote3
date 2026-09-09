"""Task-oriented clinical reporting rule authoring routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.app.container import util
from api.app.deps.services import (
    get_clinical_rule_authoring_service,
    get_clinical_rule_testing_service,
)
from api.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from api.application.reporting.clinical_rules.registry import fact_catalog_payload
from api.application.reporting.clinical_rules.testing import ClinicalRuleTestingService
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleAuthoringOptionsPayload,
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleEvaluation,
    ClinicalRuleFactsPayload,
    ClinicalRuleImportRequest,
    ClinicalRulePreviewRequest,
    ClinicalRuleRevisionDoc,
    ClinicalRuleRevisionsPayload,
    ClinicalRuleSamplePreviewPayload,
    ClinicalRuleSetDoc,
    ClinicalRuleSetListPayload,
    ClinicalRuleSetVersionsPayload,
    ClinicalRuleTestSamplesPayload,
    ClinicalRuleTransition,
    ClinicalRuleValidationResult,
)
from api.interfaces.http.tags import TAG_CLINICAL_RULES
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(prefix="/api/v1/admin/clinical-rule-sets", tags=[TAG_CLINICAL_RULES])


def _serializable(value):
    """Convert rule payloads using the shared response serializer.

    Args:
        value: Rule document, collection, or evaluation payload to serialize.

    Returns:
        The value with types converted by the shared serialization utility.
    """
    return util.common.convert_to_serializable(value)


@router.get("", response_model=ClinicalRuleSetListPayload)
def list_rule_sets(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """List rule sets with optional filters; requires `clinical_rules:view`.

    \u000c

    Args:
        status: Lifecycle status filter, or None to omit it.
        q: Search text, or None to omit text filtering.
        page: One-based result page; defaults to 1.
        per_page: Page size from 1 to 200; defaults to 30.
        _user: User authorized by the view dependency.
        service: Rule authoring service used to query the catalog.

    Returns:
        Serialized rule-set listing with pagination metadata.
    """
    return _serializable(service.list(status=status, search=q, page=page, per_page=per_page))


@router.get("/facts", response_model=ClinicalRuleFactsPayload)
def clinical_rule_facts(
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
):
    """List supported rule facts; requires `clinical_rules:view`.

    \u000c

    Args:
        _user: User authorized by the view dependency.

    Returns:
        An items envelope containing the registered fact definitions.
    """
    return {"items": fact_catalog_payload()}


@router.get("/authoring-options", response_model=ClinicalRuleAuthoringOptionsPayload)
def clinical_rule_authoring_options(
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Return rule authoring choices; requires `clinical_rules:view`.

    \u000c

    Args:
        _user: User authorized by the view dependency.
        service: Rule authoring service supplying configuration choices.

    Returns:
        Available assay scopes and rule authoring options.
    """
    return service.authoring_options()


@router.get("/versions/{document_id}/test-samples", response_model=ClinicalRuleTestSamplesPayload)
def search_clinical_rule_test_samples(
    document_id: str,
    q: str = Query(default=""),
    match_subpanel: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: ApiUser = Depends(require_access(permission="clinical_rules:test")),
    service: ClinicalRuleTestingService = Depends(get_clinical_rule_testing_service),
):
    """Find ready samples for a rule version; requires `clinical_rules:test`.

    \u000c

    Args:
        document_id: Rule-set version document identifier.
        q: Sample search text; an empty string omits text filtering.
        match_subpanel: Restrict to the rule scope's subpanel when True (default).
        page: One-based result page; defaults to 1.
        per_page: Page size from 1 to 100; defaults to 20.
        user: Authorized user whose assay and environment scopes limit results.
        service: Rule testing service used to search ready samples.

    Returns:
        Serialized sample summaries and pagination metadata.

    Raises:
        AppError: If the version is absent (404) or its assay is outside the
            user's assigned scope (403).

    Notes:
        Superusers have no user-specific assay or environment restrictions.
    """
    return _serializable(
        service.search_samples(
            document_id=document_id,
            search=q,
            match_subpanel=match_subpanel,
            allowed_asp_ids=None if user.is_superuser else user.asp_ids,
            allowed_environments=None if user.is_superuser else user.envs,
            page=page,
            per_page=per_page,
        )
    )


@router.post(
    "/versions/{document_id}/test-samples/{sample_id}/preview",
    response_model=ClinicalRuleSamplePreviewPayload,
    summary="Test a rule-set version against a sample",
)
def preview_clinical_rule_with_sample(
    document_id: str,
    sample_id: str,
    include_condition_trace: bool = False,
    user: ApiUser = Depends(require_access(permission="clinical_rules:test")),
    service: ClinicalRuleTestingService = Depends(get_clinical_rule_testing_service),
):
    """Evaluate report rules with live sample context without modifying the sample.

    Requires `clinical_rules:test` and access to the selected sample. Enable
    `include_condition_trace` to inspect how individual conditions were evaluated.
    The result is a testing preview, not a saved clinical report.
    """
    sample = _get_sample_for_api(sample_id, user)
    return _serializable(
        service.preview(
            document_id=document_id,
            sample=sample,
            include_condition_trace=include_condition_trace,
        )
    )


@router.get("/{rule_set_id}/versions", response_model=ClinicalRuleSetVersionsPayload)
def list_rule_set_versions(
    rule_set_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """List versions of a rule set; requires `clinical_rules:view`.

    \u000c

    Args:
        rule_set_id: Logical rule-set identifier shared by its versions.
        _user: User authorized by the view dependency.
        service: Rule authoring service used to retrieve versions.

    Returns:
        An items envelope containing serialized version documents.
    """
    return {"items": _serializable(service.versions(rule_set_id))}


@router.get("/versions/{document_id}", response_model=ClinicalRuleSetDoc)
def get_rule_set_version(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Read a rule-set version; requires `clinical_rules:view`.

    \u000c

    Args:
        document_id: Version document identifier, not the logical rule-set ID.
        _user: User authorized by the view dependency.
        service: Rule authoring service used to load the version.

    Returns:
        The serialized rule-set version document.

    Raises:
        AppError: If the version does not exist (404).
    """
    return _serializable(service.get(document_id))


@router.get("/versions/{document_id}/export", response_model=ClinicalRuleSetDoc)
def export_rule_set_version(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Return the canonical JSON representation of one governed version."""
    return _serializable(service.get(document_id))


@router.get(
    "/versions/{document_id}/revisions",
    response_model=ClinicalRuleRevisionsPayload,
)
def list_rule_set_revisions(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """List a version's saved revisions; requires `clinical_rules:view`.

    \u000c

    Args:
        document_id: Rule-set version document identifier.
        _user: User authorized by the view dependency.
        service: Rule authoring service used to load revision history.

    Returns:
        An items envelope containing serialized revision records.

    Raises:
        AppError: If the version does not exist (404).
    """
    return {"items": _serializable(service.revisions(document_id))}


@router.get(
    "/versions/{document_id}/revisions/{revision}",
    response_model=ClinicalRuleRevisionDoc,
)
def get_rule_set_revision(
    document_id: str,
    revision: int,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Read a saved version revision; requires `clinical_rules:view`.

    \u000c

    Args:
        document_id: Rule-set version document identifier.
        revision: Revision number to retrieve from that version's history.
        _user: User authorized by the view dependency.
        service: Rule authoring service used to retrieve the revision.

    Returns:
        The serialized revision record.

    Raises:
        AppError: If the version or revision does not exist (404).
    """
    return _serializable(service.revision(document_id, revision))


@router.post("/drafts", status_code=201, response_model=ClinicalRuleSetDoc)
def create_rule_set_draft(
    payload: ClinicalRuleDraftCreate,
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Create an editable rule-set draft for subsequent validation and review.

    Requires `clinical_rules:draft`. Creating a draft does not publish its wording
    or replace the currently published rule-set version.
    """
    return _serializable(service.create_draft(payload, actor=user.username))


@router.post("/imports", status_code=201, response_model=ClinicalRuleSetDoc)
def import_rule_set_draft(
    payload: ClinicalRuleImportRequest,
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Validate canonical JSON and create a new editable draft from it."""
    return _serializable(service.import_draft(payload, actor=user.username))


@router.patch("/drafts/{document_id}", response_model=ClinicalRuleSetDoc)
def update_rule_set_draft(
    document_id: str,
    payload: ClinicalRuleDraftUpdate,
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Save draft changes; requires `clinical_rules:draft`.

    \u000c

    Args:
        document_id: Draft version document identifier.
        payload: Expected revision and changes; None-valued fields are omitted.
        user: Authorized user recorded as the editor and audit actor.
        service: Rule authoring service that validates and persists the changes.

    Returns:
        The serialized updated draft with its incremented revision.

    Raises:
        AppError: If the version is absent (404) or the draft update conflicts (409).
        ValidationError: If the proposed document fails schema validation.
    """
    return _serializable(service.update_draft(document_id, payload, actor=user.username))


@router.delete("/drafts/{document_id}", status_code=204, response_class=Response)
def delete_rule_set_draft(
    document_id: str,
    revision: int = Query(ge=1),
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Permanently delete an editable draft; requires `clinical_rules:draft`.

    \u000c

    Args:
        document_id: Draft version document identifier.
        revision: Expected current revision, at least 1.
        user: Authorized user recorded as the deletion audit actor.
        service: Rule authoring service that deletes and audits the draft.

    Raises:
        AppError: If the version is absent (404), is not a draft, or changed
            before deletion (409).

    Notes:
        The endpoint returns HTTP 204 with no response body.
    """
    service.delete_draft(document_id, expected_revision=revision, actor=user.username)


@router.post("/drafts/{document_id}/validate", response_model=ClinicalRuleValidationResult)
def validate_rule_set_draft(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Check a rule version for validation issues; requires `clinical_rules:draft`.

    \u000c

    Args:
        document_id: Rule-set version document identifier to validate.
        _user: User authorized by the draft dependency.
        service: Rule authoring service running rule validation.

    Returns:
        Validation status and reported rule issues without a lifecycle transition.

    Raises:
        AppError: If the version does not exist (404).
    """
    return service.validate(document_id)


@router.post("/drafts/{document_id}/preview", response_model=ClinicalRuleEvaluation)
def preview_rule_set_draft(
    document_id: str,
    payload: ClinicalRulePreviewRequest,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Evaluate a version against supplied facts; requires `clinical_rules:draft`.

    \u000c

    Args:
        document_id: Rule-set version document identifier to evaluate.
        payload: Facts validated as a prepared report context by the service.
        _user: User authorized by the draft dependency.
        service: Rule authoring service running the evaluation.

    Returns:
        Serialized evaluation using the version's declared reporting analyses.

    Raises:
        AppError: If the version does not exist (404).
        ValidationError: If the facts do not form a valid prepared report context.

    Notes:
        The evaluation is not persisted as a report or rule-set update.
    """
    return _serializable(service.preview(document_id, payload.facts))


@router.post("/drafts/{document_id}/submit", response_model=ClinicalRuleSetDoc)
def submit_rule_set_draft(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:submit")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Submit a valid draft for review; requires `clinical_rules:submit`.

    \u000c

    Args:
        document_id: Draft version document identifier.
        payload: Transition reason and assigned clinical reviewer.
        user: Authorized submitter recorded in the lifecycle and audit history.
        service: Rule authoring service handling validation and submission.

    Returns:
        The serialized submitted version.

    Raises:
        AppError: If the version is absent (404), validation fails (422), the
            reviewer is missing (400), or assignment or state conflicts (409).

    Notes:
        The service records submission and notifies the assigned reviewer.
    """
    return _serializable(service.submit(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/start-clinical-review", response_model=ClinicalRuleSetDoc)
def start_rule_set_clinical_review(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:clinical_review")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Start an assigned review; requires `clinical_rules:clinical_review`.

    \u000c

    Args:
        document_id: Submitted version document identifier.
        payload: Transition reason; the assignee field is not used here.
        user: Authorized user who must be the assigned clinical reviewer.
        service: Rule authoring service recording the review transition.

    Returns:
        The serialized version in clinical review.

    Raises:
        AppError: If the version is absent (404), another reviewer is assigned,
            or the version is not submitted (409).
    """
    return _serializable(service.start_review(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/clinical-review", response_model=ClinicalRuleSetDoc)
def decide_rule_set_clinical_review(
    document_id: str,
    payload: ClinicalRuleDecision,
    user: ApiUser = Depends(require_access(permission="clinical_rules:clinical_review")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Record a clinical decision; requires `clinical_rules:clinical_review`.

    \u000c

    Args:
        document_id: Version document identifier currently in clinical review.
        payload: Approval decision, reason, and publisher for an approval.
        user: Assigned reviewer, who cannot be the latest content editor.
        service: Rule authoring service recording the decision and notifications.

    Returns:
        The serialized approved or rejected version.

    Raises:
        AppError: If the version is absent (404), an approval lacks a publisher
            (400), or the actor, publisher eligibility, or state conflicts (409).

    Notes:
        Approval notifies the publisher; rejection notifies the draft creator.
    """
    return _serializable(service.clinical_decision(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/publish", response_model=ClinicalRuleSetDoc)
def publish_rule_set(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:publish")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Publish an approved rule version; requires `clinical_rules:publish`.

    \u000c

    Args:
        document_id: Approved version document identifier.
        payload: Publication reason; the assignee field is not used here.
        user: Authorized user who must be the assigned publisher.
        service: Rule authoring service validating and publishing the version.

    Returns:
        The serialized active, published version with its content hash.

    Raises:
        AppError: If the version is absent (404), validation fails (422), or
            approval, editor independence, publisher, or state checks fail (409).

    Notes:
        The service audits publication and notifies the creator when different
        from the publisher.
    """
    return _serializable(service.publish(document_id, payload, actor=user.username))


@router.post("/versions/{document_id}/retire", response_model=ClinicalRuleSetDoc)
def retire_rule_set(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:retire")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    """Retire a published rule version; requires `clinical_rules:retire`.

    \u000c

    Args:
        document_id: Published version document identifier.
        payload: Required retirement reason; the assignee field is not used here.
        user: Authorized user recorded as the retiring actor.
        service: Rule authoring service recording retirement and its audit event.

    Returns:
        The serialized retired version with active set to False.

    Raises:
        AppError: If the reason is empty (400) or the version cannot transition
            from published to retired (409).
    """
    return _serializable(service.retire(document_id, payload, actor=user.username))
