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
    return _serializable(service.list(status=status, search=q, page=page, per_page=per_page))


@router.get("/facts", response_model=ClinicalRuleFactsPayload)
def clinical_rule_facts(
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
):
    return {"items": fact_catalog_payload()}


@router.get("/authoring-options", response_model=ClinicalRuleAuthoringOptionsPayload)
def clinical_rule_authoring_options(
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
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
)
def preview_clinical_rule_with_sample(
    document_id: str,
    sample_id: str,
    include_condition_trace: bool = False,
    user: ApiUser = Depends(require_access(permission="clinical_rules:test")),
    service: ClinicalRuleTestingService = Depends(get_clinical_rule_testing_service),
):
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
    return {"items": _serializable(service.versions(rule_set_id))}


@router.get("/versions/{document_id}", response_model=ClinicalRuleSetDoc)
def get_rule_set_version(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:view")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
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
    return _serializable(service.revision(document_id, revision))


@router.post("/drafts", status_code=201, response_model=ClinicalRuleSetDoc)
def create_rule_set_draft(
    payload: ClinicalRuleDraftCreate,
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
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
    return _serializable(service.update_draft(document_id, payload, actor=user.username))


@router.delete("/drafts/{document_id}", status_code=204, response_class=Response)
def delete_rule_set_draft(
    document_id: str,
    revision: int = Query(ge=1),
    user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    service.delete_draft(document_id, expected_revision=revision, actor=user.username)


@router.post("/drafts/{document_id}/validate", response_model=ClinicalRuleValidationResult)
def validate_rule_set_draft(
    document_id: str,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return service.validate(document_id)


@router.post("/drafts/{document_id}/preview", response_model=ClinicalRuleEvaluation)
def preview_rule_set_draft(
    document_id: str,
    payload: ClinicalRulePreviewRequest,
    _user: ApiUser = Depends(require_access(permission="clinical_rules:draft")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.preview(document_id, payload.facts))


@router.post("/drafts/{document_id}/submit", response_model=ClinicalRuleSetDoc)
def submit_rule_set_draft(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:submit")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.submit(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/start-clinical-review", response_model=ClinicalRuleSetDoc)
def start_rule_set_clinical_review(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:clinical_review")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.start_review(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/clinical-review", response_model=ClinicalRuleSetDoc)
def decide_rule_set_clinical_review(
    document_id: str,
    payload: ClinicalRuleDecision,
    user: ApiUser = Depends(require_access(permission="clinical_rules:clinical_review")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.clinical_decision(document_id, payload, actor=user.username))


@router.post("/drafts/{document_id}/publish", response_model=ClinicalRuleSetDoc)
def publish_rule_set(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:publish")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.publish(document_id, payload, actor=user.username))


@router.post("/versions/{document_id}/retire", response_model=ClinicalRuleSetDoc)
def retire_rule_set(
    document_id: str,
    payload: ClinicalRuleTransition,
    user: ApiUser = Depends(require_access(permission="clinical_rules:retire")),
    service: ClinicalRuleAuthoringService = Depends(get_clinical_rule_authoring_service),
):
    return _serializable(service.retire(document_id, payload, actor=user.username))
