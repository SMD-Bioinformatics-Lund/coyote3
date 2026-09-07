"""Canonical RNA router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.app.container import util
from api.app.deps.services import get_rna_service
from api.application.common.change_payload import change_payload
from api.application.rna.expression_analysis import RnaService
from api.contracts.rna import (
    RnaAnalysisPayload,
    RnaCsvExportContextPayload,
    RnaFusionContextPayload,
    RnaFusionListPayload,
)
from api.contracts.samples import SampleChangePayload, SampleCommentSuggestionPayload
from api.domain.common.errors import setup_error
from api.interfaces.http.clinical.common.change_helpers import comment_change, resource_change
from api.interfaces.http.tags import TAG_RNA_FUSIONS
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=[TAG_RNA_FUSIONS])


def _require_rna_sample(sample: dict, sample_id: str) -> None:
    """Reject RNA fusion requests for samples that do not have RNA analysis data."""
    if str(sample.get("omics_layer") or "").lower() != "rna":
        raise setup_error(
            "RNA fusion analysis is unavailable for this sample",
            (
                f"Sample '{sample.get('name') or sample_id}' has omics layer "
                f"'{sample.get('omics_layer') or 'unknown'}'. RNA fusion endpoints require an RNA sample."
            ),
        )


def _fusion_flag_change(
    *, sample_id: str, fusion_id: str, user: ApiUser, service: RnaService, flag: str, apply: bool
):
    action = f"{'mark' if apply else 'unmark'}_{flag}"
    return resource_change(
        sample_id,
        fusion_id,
        user,
        service,
        resource="fusion",
        action=action,
        mutate=lambda: service.set_fusion_flag(fusion_id=fusion_id, apply=apply, flag=flag),
    )


@router.get("/api/v1/samples/{sample_id}/fusions", response_model=RnaFusionListPayload)
def list_rna_fusions(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Return fusions for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    _require_rna_sample(sample, sample_id)
    return util.common.convert_to_serializable(
        service.list_fusions_payload(request=request, sample=sample, util_module=util)
    )


@router.get(
    "/api/v1/samples/{sample_id}/rna-analysis",
    response_model=RnaAnalysisPayload,
    summary="Read RNA expression, classification, and quality results",
)
def read_rna_analysis(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Return the ingested non-fusion RNA analysis records for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    _require_rna_sample(sample, sample_id)
    return util.common.convert_to_serializable(service.rna_analysis_payload(sample=sample))


@router.get(
    "/api/v1/samples/{sample_id}/fusions/comment-suggestion",
    response_model=SampleCommentSuggestionPayload,
    summary="Generate a filtered RNA sample-comment suggestion",
)
def rna_sample_comment_suggestion(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Return the established RNA summary text for the current sample filters."""
    sample = _get_sample_for_api(sample_id, user)
    _require_rna_sample(sample, sample_id)
    payload = service.list_fusions_payload(
        request=request,
        sample=sample,
        util_module=util,
        paginate=False,
    )
    return util.common.convert_to_serializable(
        {
            "sample_id": str(sample.get("_id")),
            "sample_name": str(sample.get("name") or sample_id),
            "analysis": "rna",
            "suggested_text": str(payload.get("ai_text") or ""),
        }
    )


@router.get(
    "/api/v1/samples/{sample_id}/fusions/exports/context",
    response_model=RnaCsvExportContextPayload,
)
def export_rna_fusions_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Return backend-generated CSV content for the current filtered fusion set."""
    sample = _get_sample_for_api(sample_id, user)
    _require_rna_sample(sample, sample_id)
    payload = service.list_fusions_payload(
        request=request, sample=sample, util_module=util, paginate=False
    )
    rows = service.build_fusion_export_rows(payload.get("fusions", []))
    return util.common.convert_to_serializable(
        {
            "filename": f"{sample.get('name', sample_id)}.filtered.fusions.csv",
            "content": service.export_rows_to_csv(rows),
            "row_count": len(rows),
        }
    )


@router.get(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}", response_model=RnaFusionContextPayload
)
def show_rna_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Return fusion detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_fusion_payload(sample=sample, fusion_id=fusion_id)
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark fusion false-positive",
)
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Mark a fusion as false positive."""
    return resource_change(
        sample_id,
        fusion_id,
        user,
        service,
        resource="fusion",
        action="mark_false_positive",
        mutate=lambda: service.set_fusion_flag(
            fusion_id=fusion_id, apply=True, flag="false_positive"
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from fusion",
)
def unmark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Remove the false-positive flag from a fusion."""
    return resource_change(
        sample_id,
        fusion_id,
        user,
        service,
        resource="fusion",
        action="unmark_false_positive",
        mutate=lambda: service.set_fusion_flag(
            fusion_id=fusion_id, apply=False, flag="false_positive"
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark fusion as interesting",
)
def mark_interesting_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Mark a fusion as interesting for clinical review."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="interesting",
        apply=True,
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove fusion interesting flag",
)
def unmark_interesting_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Remove the fusion's interesting review marker."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="interesting",
        apply=False,
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Mark fusion irrelevant",
)
def mark_irrelevant_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Mark a fusion irrelevant for the current review."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="irrelevant",
        apply=True,
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Restore irrelevant fusion",
)
def unmark_irrelevant_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Restore an irrelevant fusion to the active review set."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="irrelevant",
        apply=False,
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/blacklisted",
    response_model=SampleChangePayload,
    summary="Blacklist fusion for sample",
)
def mark_blacklisted_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Apply the sample-specific structural blacklist state."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="blacklisted",
        apply=True,
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/blacklisted",
    response_model=SampleChangePayload,
    summary="Remove sample fusion blacklist",
)
def unmark_blacklisted_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Remove the sample-specific structural blacklist state."""
    return _fusion_flag_change(
        sample_id=sample_id,
        fusion_id=fusion_id,
        user=user,
        service=service,
        flag="blacklisted",
        apply=False,
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/selection/{callidx}/{num_calls}",
    response_model=SampleChangePayload,
    summary="Select fusion call",
)
def pick_fusion_call(
    sample_id: str,
    fusion_id: str,
    callidx: str,
    num_calls: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Persist selected fusion call index."""
    return resource_change(
        sample_id,
        fusion_id,
        user,
        service,
        resource="fusion",
        action="pick_fusion_call",
        mutate=lambda: service.select_fusion_call(
            fusion_id=fusion_id, callidx=callidx, num_calls=num_calls
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide fusion comment",
)
def hide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Hide a fusion comment."""
    return comment_change(
        sample_id,
        fusion_id,
        comment_id,
        user,
        service,
        resource="fusion_comment",
        action="hide",
        mutate=lambda: service.set_fusion_comment_hidden(
            fusion_id=fusion_id, comment_id=comment_id, hidden=True
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide fusion comment",
)
def unhide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access()),
    service: RnaService = Depends(get_rna_service),
):
    """Unhide a fusion comment."""
    return comment_change(
        sample_id,
        fusion_id,
        comment_id,
        user,
        service,
        resource="fusion_comment",
        action="unhide",
        mutate=lambda: service.set_fusion_comment_hidden(
            fusion_id=fusion_id, comment_id=comment_id, hidden=False
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Bulk false-positive fusion update",
)
def set_fusion_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Apply bulk false-positive flag updates for fusions."""
    _get_sample_for_api(sample_id, user)
    operation = service.set_fusion_bulk_flag(
        fusion_ids=fusion_ids, apply=apply, flag="false_positive"
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_false_positive_bulk",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Bulk irrelevant fusion update",
)
def set_fusion_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Apply bulk irrelevant flag updates for fusions."""
    _get_sample_for_api(sample_id, user)
    operation = service.set_fusion_bulk_flag(fusion_ids=fusion_ids, apply=apply, flag="irrelevant")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_irrelevant_bulk",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/flags/blacklisted",
    response_model=SampleChangePayload,
    summary="Bulk sample-specific fusion blacklist update",
)
def set_fusion_blacklisted_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: RnaService = Depends(get_rna_service),
):
    """Apply or remove sample-specific blacklist state for selected fusions."""
    _get_sample_for_api(sample_id, user)
    operation = service.set_fusion_bulk_flag(fusion_ids=fusion_ids, apply=apply, flag="blacklisted")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_blacklisted_bulk",
            operation=operation,
        )
    )
