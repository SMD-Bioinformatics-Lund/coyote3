"""Canonical RNA router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_fusions
from api.interfaces.http.tags import TAG_RNA_FUSIONS
from api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.clinical import Findings
from coyote3.contracts.rna import (
    RnaAnalysisPayload,
    RnaCsvExportContextPayload,
    RnaFusionContextPayload,
    RnaFusionListPayload,
)
from coyote3.contracts.samples import SampleChangePayload, SampleCommentSuggestionPayload

router = APIRouter(tags=[TAG_RNA_FUSIONS])


@router.get("/api/v1/samples/{sample_id}/fusions", response_model=RnaFusionListPayload)
def list_rna_fusions(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_fusions),
):
    """Return fusions for a sample."""
    return util.common.convert_to_serializable(service.view(analysis_query_from_request(request)))


@router.get(
    "/api/v1/samples/{sample_id}/rna-analysis",
    response_model=RnaAnalysisPayload,
    summary="Read RNA expression, classification, and quality results",
)
def read_rna_analysis(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_fusions),
):
    """Return the ingested non-fusion RNA analysis records for a sample."""
    return util.common.convert_to_serializable(service.analysis())


@router.get(
    "/api/v1/samples/{sample_id}/fusions/comment-suggestion",
    response_model=SampleCommentSuggestionPayload,
    summary="Generate a filtered RNA sample-comment suggestion",
)
def rna_sample_comment_suggestion(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_fusions),
):
    """Return the established RNA summary text for the current sample filters."""
    return util.common.convert_to_serializable(
        service.comment_suggestion(analysis_query_from_request(request))
    )


@router.get(
    "/api/v1/samples/{sample_id}/fusions/exports/context",
    response_model=RnaCsvExportContextPayload,
)
def export_rna_fusions_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_fusions),
):
    """Return backend-generated CSV content for the current filtered fusion set."""
    return util.common.convert_to_serializable(
        service.export_csv(analysis_query_from_request(request)).model_dump()
    )


@router.get(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}", response_model=RnaFusionContextPayload
)
def show_rna_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_fusions),
):
    """Return fusion detail payload."""
    return util.common.convert_to_serializable(service.context(fusion_id))


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark fusion false-positive",
)
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: Findings = Depends(get_fusions),
):
    """Mark a fusion as false positive."""
    operation = service.set_flag(fusion_id, flag="false_positive", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="mark_false_positive",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Remove the false-positive flag from a fusion."""
    operation = service.set_flag(fusion_id, flag="false_positive", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="unmark_false_positive",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Mark a fusion as interesting for clinical review."""
    operation = service.set_flag(fusion_id, flag="interesting", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="mark_interesting",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Remove the fusion's interesting review marker."""
    operation = service.set_flag(fusion_id, flag="interesting", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="unmark_interesting",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Mark a fusion irrelevant for the current review."""
    operation = service.set_flag(fusion_id, flag="irrelevant", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="mark_irrelevant",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Restore an irrelevant fusion to the active review set."""
    operation = service.set_flag(fusion_id, flag="irrelevant", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="unmark_irrelevant",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Apply the sample-specific structural blacklist state."""
    operation = service.set_flag(fusion_id, flag="blacklisted", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="mark_blacklisted",
            operation=operation,
        )
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
    service: Findings = Depends(get_fusions),
):
    """Remove the sample-specific structural blacklist state."""
    operation = service.set_flag(fusion_id, flag="blacklisted", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action="unmark_blacklisted",
            operation=operation,
        )
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
    user: ApiUser = Depends(require_access(permission="fusion:manage")),
    service: Findings = Depends(get_fusions),
):
    """Persist selected fusion call index."""
    service.select_fusion_call(fusion_id, call_index=callidx, number_of_calls=num_calls)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="fusion", resource_id=fusion_id, action="pick_fusion_call"
        )
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
    user: ApiUser = Depends(require_access(permission="variant.comment:hide")),
    service: Findings = Depends(get_fusions),
):
    """Hide a fusion comment."""
    service.set_comment_hidden(fusion_id, comment_id, hidden=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="fusion_comment", resource_id=comment_id, action="hide"
        )
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
    user: ApiUser = Depends(require_access(permission="variant.comment:unhide")),
    service: Findings = Depends(get_fusions),
):
    """Unhide a fusion comment."""
    service.set_comment_hidden(fusion_id, comment_id, hidden=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="fusion_comment", resource_id=comment_id, action="unhide"
        )
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
    service: Findings = Depends(get_fusions),
):
    """Apply bulk false-positive flag updates for fusions."""
    operation = service.set_bulk_flags(fusion_ids, flag="false_positive", value=apply)
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
    service: Findings = Depends(get_fusions),
):
    """Apply bulk irrelevant flag updates for fusions."""
    operation = service.set_bulk_flags(fusion_ids, flag="irrelevant", value=apply)
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
    service: Findings = Depends(get_fusions),
):
    """Apply or remove sample-specific blacklist state for selected fusions."""
    operation = service.set_bulk_flags(fusion_ids, flag="blacklisted", value=apply)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_blacklisted_bulk",
            operation=operation,
        )
    )
