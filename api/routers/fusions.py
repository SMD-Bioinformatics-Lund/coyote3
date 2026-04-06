"""Canonical RNA router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.contracts.rna import RnaFusionContextPayload, RnaFusionListPayload
from api.contracts.samples import SampleChangePayload
from api.deps.services import get_rna_service
from api.extensions import util
from api.routers.change_helpers import comment_change, resource_change
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.common.change_payload import change_payload
from api.services.rna.expression_analysis import RnaService

router = APIRouter(tags=["fusions"])


@router.get("/api/v1/samples/{sample_id}/fusions", response_model=RnaFusionListPayload)
def list_rna_fusions(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """Return fusions for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_fusions_payload(request=request, sample=sample, util_module=util)
    )


@router.get(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}", response_model=RnaFusionContextPayload
)
def show_rna_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
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
    user: ApiUser = Depends(require_access(min_level=1)),
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
    user: ApiUser = Depends(require_access(min_level=1)),
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
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/selection/{callidx}/{num_calls}",
    response_model=SampleChangePayload,
    summary="Select fusion call",
)
def pick_fusion_call(
    sample_id: str,
    fusion_id: str,
    callidx: str,
    num_calls: str,
    user: ApiUser = Depends(require_access(min_level=1)),
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
    user: ApiUser = Depends(require_access(min_level=1)),
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
    user: ApiUser = Depends(require_access(min_level=1)),
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
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """Apply bulk false-positive flag updates for fusions."""
    _get_sample_for_api(sample_id, user)
    service.set_fusion_bulk_flag(fusion_ids=fusion_ids, apply=apply, flag="false_positive")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_false_positive_bulk",
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
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """Apply bulk irrelevant flag updates for fusions."""
    _get_sample_for_api(sample_id, user)
    service.set_fusion_bulk_flag(fusion_ids=fusion_ids, apply=apply, flag="irrelevant")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_irrelevant_bulk",
        )
    )
