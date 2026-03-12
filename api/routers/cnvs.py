"""Canonical CNV router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import DnaCnvContextPayload, DnaCnvListPayload
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_cnv_service
from api.extensions import util
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.cnv_service import CnvService

router = APIRouter(tags=["cnvs"])

if not hasattr(util, "common"):
    util.init_util()


@router.get("/api/v1/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: CnvService = Depends(get_cnv_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.list_cnvs_payload(request=request, sample=sample, util_module=util))


@router.get("/api/v1/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: CnvService = Depends(get_cnv_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.show_cnv_payload(sample=sample, cnv_id=cnv_id, util_module=util))


@router.delete("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting", response_model=SampleMutationPayload, summary="Remove interesting flag from CNV")
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unmark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_interesting")
    )


@router.patch("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting", response_model=SampleMutationPayload, summary="Mark CNV interesting")
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.mark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_interesting")
    )


@router.patch("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Mark CNV false-positive")
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.mark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_false_positive")
    )


@router.delete("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Remove false-positive flag from CNV")
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_false_positive")
    )


@router.patch("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy", response_model=SampleMutationPayload, summary="Mark CNV noteworthy")
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.noteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_noteworthy")
    )


@router.delete("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy", response_model=SampleMutationPayload, summary="Remove noteworthy flag from CNV")
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unnoteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_noteworthy")
    )


@router.patch("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Hide CNV comment")
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_variant_comment", min_role="manager", min_level=99)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="hide")
    )


@router.delete("/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Unhide CNV comment")
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)),
    service: CnvService = Depends(get_cnv_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="unhide")
    )
