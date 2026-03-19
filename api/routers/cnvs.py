"""Canonical CNV router module."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import DnaCnvContextPayload, DnaCnvListPayload
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_cnv_service
from api.extensions import util
from api.routers.mutation_helpers import run_serialized_mutation
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.cnv_service import CnvService

router = APIRouter(tags=["cnvs"])

if not hasattr(util, "common"):
    util.init_util()


def _cnv_mutation(
    sample_id: str,
    cnv_id: str,
    user: ApiUser,
    service: CnvService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a CNV mutation and return the canonical mutation payload."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action=action,
        ),
        util_module=util,
    )


def _cnv_comment_mutation(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser,
    service: CnvService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a CNV comment visibility mutation."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="cnv_comment",
            resource_id=comment_id,
            action=action,
        ),
        util_module=util,
    )


@router.get("/api/v1/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: CnvService = Depends(get_cnv_service),
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
    service: CnvService = Depends(get_cnv_service),
):
    """Return CNV detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_cnv_payload(sample=sample, cnv_id=cnv_id, util_module=util)
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleMutationPayload,
    summary="Remove interesting flag from CNV",
)
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Remove the interesting flag from a CNV."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="unmark_interesting",
        mutate=lambda: service.repository.cnv_handler.unmark_interesting_cnv(cnv_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleMutationPayload,
    summary="Mark CNV interesting",
)
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Mark a CNV as interesting."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="mark_interesting",
        mutate=lambda: service.repository.cnv_handler.mark_interesting_cnv(cnv_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleMutationPayload,
    summary="Mark CNV false-positive",
)
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Mark a CNV as false positive."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="mark_false_positive",
        mutate=lambda: service.repository.cnv_handler.mark_false_positive_cnv(cnv_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleMutationPayload,
    summary="Remove false-positive flag from CNV",
)
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Remove the false-positive flag from a CNV."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="unmark_false_positive",
        mutate=lambda: service.repository.cnv_handler.unmark_false_positive_cnv(cnv_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleMutationPayload,
    summary="Mark CNV noteworthy",
)
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Mark a CNV as noteworthy."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="mark_noteworthy",
        mutate=lambda: service.repository.cnv_handler.noteworthy_cnv(cnv_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleMutationPayload,
    summary="Remove noteworthy flag from CNV",
)
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    """Remove the noteworthy flag from a CNV."""
    return _cnv_mutation(
        sample_id,
        cnv_id,
        user,
        service,
        action="unmark_noteworthy",
        mutate=lambda: service.repository.cnv_handler.unnoteworthy_cnv(cnv_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Hide CNV comment",
)
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
    service: CnvService = Depends(get_cnv_service),
):
    """Hide a CNV comment."""
    return _cnv_comment_mutation(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        action="hide",
        mutate=lambda: service.repository.cnv_handler.hide_cnvs_comment(cnv_id, comment_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Unhide CNV comment",
)
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
    service: CnvService = Depends(get_cnv_service),
):
    """Unhide a CNV comment."""
    return _cnv_comment_mutation(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        action="unhide",
        mutate=lambda: service.repository.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id),
    )
