"""Canonical RNA router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.contracts.rna import RnaFusionContextPayload, RnaFusionListPayload
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_rna_service
from api.extensions import util
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.rna_service import RnaService

router = APIRouter(tags=["fusions"])
if not hasattr(util, "common"):
    util.init_util()


@router.get("/api/v1/samples/{sample_id}/fusions", response_model=RnaFusionListPayload)
def list_rna_fusions(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: RnaService = Depends(get_rna_service),
):
    """List rna fusions.

    Args:
        request (Request): Value for ``request``.
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
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
    """Show rna fusion.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
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
    """Handle mark false positive fusion.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    service.repository.fusion_handler.mark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion", resource_id=fusion_id, action="mark_false_positive"
        )
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
    """Handle unmark false positive fusion.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    service.repository.fusion_handler.unmark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion", resource_id=fusion_id, action="unmark_false_positive"
        )
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
    """Handle pick fusion call.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        callidx (str): Value for ``callidx``.
        num_calls (str): Value for ``num_calls``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    service.repository.fusion_handler.pick_fusion(fusion_id, callidx, num_calls)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion", resource_id=fusion_id, action="pick_fusion_call"
        )
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
    """Handle hide fusion comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        comment_id (str): Value for ``comment_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    service.repository.fusion_handler.hide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion_comment", resource_id=comment_id, action="hide"
        )
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
    """Handle unhide fusion comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        fusion_id (str): Value for ``fusion_id``.
        comment_id (str): Value for ``comment_id``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    service.repository.fusion_handler.unhide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion_comment", resource_id=comment_id, action="unhide"
        )
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
    """Set fusion false positive bulk.

    Args:
        sample_id (str): Value for ``sample_id``.
        apply (bool): Value for ``apply``.
        fusion_ids (list[str]): Value for ``fusion_ids``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        service.repository.fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion_bulk", resource_id="bulk", action="set_false_positive_bulk"
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
    """Set fusion irrelevant bulk.

    Args:
        sample_id (str): Value for ``sample_id``.
        apply (bool): Value for ``apply``.
        fusion_ids (list[str]): Value for ``fusion_ids``.
        user (ApiUser): Value for ``user``.
        service (RnaService): Value for ``service``.

    Returns:
        The function result.
    """
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        service.repository.fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        service.mutation_payload(
            sample_id, resource="fusion_bulk", resource_id="bulk", action="set_irrelevant_bulk"
        )
    )
