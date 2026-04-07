"""Canonical CNV router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import DnaCnvContextPayload, DnaCnvListPayload
from api.contracts.samples import SampleChangePayload
from api.deps.services import get_dna_structural_service
from api.extensions import util
from api.routers.change_helpers import comment_change, resource_change
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.dna.structural_variants import DnaStructuralService

router = APIRouter(tags=["cnvs"])


@router.get("/api/v1/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return CNVs for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_cnvs_payload(request=request, sample=sample, util_module=util)
    )


@router.get("/api/v1/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return CNV detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_cnv_payload(sample=sample, cnv_id=cnv_id, util_module=util)
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from CNV",
)
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the interesting flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_interesting",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="interesting"),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark CNV interesting",
)
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as interesting."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_interesting",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="interesting"),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark CNV false-positive",
)
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as false positive."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_false_positive",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="false_positive"),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from CNV",
)
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the false-positive flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_false_positive",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="false_positive"),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleChangePayload,
    summary="Mark CNV noteworthy",
)
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as noteworthy."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_noteworthy",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="noteworthy"),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleChangePayload,
    summary="Remove noteworthy flag from CNV",
)
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the noteworthy flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_noteworthy",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="noteworthy"),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide CNV comment",
)
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Hide a CNV comment."""
    return comment_change(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        resource="cnv_comment",
        action="hide",
        mutate=lambda: service.set_cnv_comment_hidden(
            cnv_id=cnv_id, comment_id=comment_id, hidden=True
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide CNV comment",
)
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Unhide a CNV comment."""
    return comment_change(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        resource="cnv_comment",
        action="unhide",
        mutate=lambda: service.set_cnv_comment_hidden(
            cnv_id=cnv_id, comment_id=comment_id, hidden=False
        ),
    )
