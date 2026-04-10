"""Canonical translocation router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import DnaTranslocationContextPayload, DnaTranslocationsPayload
from api.contracts.samples import SampleChangePayload
from api.deps.services import get_dna_structural_service
from api.extensions import util
from api.routers.change_helpers import comment_change, resource_change
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.dna.structural_variants import DnaStructuralService

router = APIRouter(tags=["translocations"])


@router.get("/api/v1/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return translocations for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_translocations_payload(request=request, sample=sample)
    )


@router.get(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return translocation detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_translocation_payload(sample=sample, transloc_id=transloc_id, util_module=util)
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark translocation interesting",
)
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="translocation:manage", min_role="user", min_level=9)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a translocation as interesting."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="mark_interesting",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=True, flag="interesting"
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from translocation",
)
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="translocation:manage", min_role="user", min_level=9)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the interesting flag from a translocation."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="unmark_interesting",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=False, flag="interesting"
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark translocation false-positive",
)
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="translocation:manage", min_role="user", min_level=9)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a translocation as false positive."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="mark_false_positive",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=True, flag="false_positive"
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from translocation",
)
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="translocation:manage", min_role="user", min_level=9)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the false-positive flag from a translocation."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="unmark_false_positive",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=False, flag="false_positive"
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide translocation comment",
)
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="variant.comment:hide", min_role="manager", min_level=99)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Hide a translocation comment."""
    return comment_change(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        resource="translocation_comment",
        action="hide",
        mutate=lambda: service.set_translocation_comment_hidden(
            transloc_id=transloc_id, comment_id=comment_id, hidden=True
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide translocation comment",
)
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="variant.comment:unhide", min_role="manager", min_level=99)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Unhide a translocation comment."""
    return comment_change(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        resource="translocation_comment",
        action="unhide",
        mutate=lambda: service.set_translocation_comment_hidden(
            transloc_id=transloc_id, comment_id=comment_id, hidden=False
        ),
    )
