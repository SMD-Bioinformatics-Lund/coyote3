"""Canonical RNA router module."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request

from api.contracts.rna import RnaFusionContextPayload, RnaFusionListPayload
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_rna_service
from api.extensions import util
from api.routers.mutation_helpers import run_serialized_mutation
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.rna_service import RnaService

router = APIRouter(tags=["fusions"])
if not hasattr(util, "common"):
    util.init_util()


def _fusion_mutation(
    sample_id: str,
    fusion_id: str,
    user: ApiUser,
    service: RnaService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a fusion mutation and return the canonical mutation payload."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="fusion",
            resource_id=fusion_id,
            action=action,
        ),
        util_module=util,
    )


def _fusion_comment_mutation(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser,
    service: RnaService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a fusion comment visibility mutation."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="fusion_comment",
            resource_id=comment_id,
            action=action,
        ),
        util_module=util,
    )


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
    response_model=SampleMutationPayload,
    summary="Mark fusion false-positive",
)
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """Mark a fusion as false positive."""
    return _fusion_mutation(
        sample_id,
        fusion_id,
        user,
        service,
        action="mark_false_positive",
        mutate=lambda: service.repository.fusion_handler.mark_false_positive_fusion(fusion_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive",
    response_model=SampleMutationPayload,
    summary="Remove false-positive flag from fusion",
)
def unmark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """Remove the false-positive flag from a fusion."""
    return _fusion_mutation(
        sample_id,
        fusion_id,
        user,
        service,
        action="unmark_false_positive",
        mutate=lambda: service.repository.fusion_handler.unmark_false_positive_fusion(fusion_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/selection/{callidx}/{num_calls}",
    response_model=SampleMutationPayload,
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
    return _fusion_mutation(
        sample_id,
        fusion_id,
        user,
        service,
        action="pick_fusion_call",
        mutate=lambda: service.repository.fusion_handler.pick_fusion(fusion_id, callidx, num_calls),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
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
    return _fusion_comment_mutation(
        sample_id,
        fusion_id,
        comment_id,
        user,
        service,
        action="hide",
        mutate=lambda: service.repository.fusion_handler.hide_fus_comment(fusion_id, comment_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
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
    return _fusion_comment_mutation(
        sample_id,
        fusion_id,
        comment_id,
        user,
        service,
        action="unhide",
        mutate=lambda: service.repository.fusion_handler.unhide_fus_comment(fusion_id, comment_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/flags/false-positive",
    response_model=SampleMutationPayload,
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
    if fusion_ids:
        service.repository.fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_false_positive_bulk",
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/fusions/flags/irrelevant",
    response_model=SampleMutationPayload,
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
    if fusion_ids:
        service.repository.fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id,
            resource="fusion_bulk",
            resource_id="bulk",
            action="set_irrelevant_bulk",
        )
    )
