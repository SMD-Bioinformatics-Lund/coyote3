"""Canonical DNA structural router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import (
    DnaCnvContextPayload,
    DnaCnvListPayload,
    DnaTranslocationContextPayload,
    DnaTranslocationsPayload,
)
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_dna_structural_service
from api.extensions import util
from api.services.dna_structural_service import DnaStructuralService
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["dna-structural"])

if not hasattr(util, "common"):
    util.init_util()


@router.get("/api/v1/dna/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.list_cnvs_payload(request=request, sample=sample, util_module=util))


@router.get("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.show_cnv_payload(sample=sample, cnv_id=cnv_id, util_module=util))


@router.get("/api/v1/dna/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.list_translocations_payload(request=request, sample=sample))


@router.get(
    "/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_translocation_payload(sample=sample, transloc_id=transloc_id, util_module=util)
    )


@router.delete("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting", response_model=SampleMutationPayload, summary="Remove interesting flag from CNV")
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unmark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_interesting")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting", response_model=SampleMutationPayload, summary="Mark CNV interesting")
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.mark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_interesting")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Mark CNV false-positive")
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.mark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_false_positive")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Remove false-positive flag from CNV")
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_false_positive")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy", response_model=SampleMutationPayload, summary="Mark CNV noteworthy")
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.noteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_noteworthy")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy", response_model=SampleMutationPayload, summary="Remove noteworthy flag from CNV")
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unnoteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_noteworthy")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Hide CNV comment")
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_variant_comment", min_role="manager", min_level=99)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="hide")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Unhide CNV comment")
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="unhide")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/interesting", response_model=SampleMutationPayload, summary="Mark translocation interesting")
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.mark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="mark_interesting")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/interesting", response_model=SampleMutationPayload, summary="Remove interesting flag from translocation")
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.unmark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="unmark_interesting")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Mark translocation false-positive")
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.mark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="mark_false_positive")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Remove false-positive flag from translocation")
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.unmark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="unmark_false_positive")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Hide translocation comment")
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_variant_comment", min_role="manager", min_level=99)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="hide")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Unhide translocation comment")
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    _get_sample_for_api(sample_id, user)
    service.repository.transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="unhide")
    )
