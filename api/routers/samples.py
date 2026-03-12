"""Sample and coverage mutation router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from api.core.interpretation.report_summary import create_comment_doc
from api.core.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.core.samples.ports import SamplesRepository
from api.core.workflows.filter_normalization import normalize_dna_filter_keys, normalize_rna_filter_keys
from api.deps.repositories import get_sample_repository
from api.extensions import util
from api.http import api_error, get_formatted_assay_config
from api.contracts.samples import (
    CoverageBlacklistStatusPayload,
    CoverageBlacklistUpdateRequest,
    SampleCommentCreateRequest,
    SampleFiltersUpdateRequest,
    SampleMutationPayload,
)
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["samples"])


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _add_sample_comment(
    sample_id: str,
    payload: SampleCommentCreateRequest,
    user: ApiUser,
    repository: SamplesRepository,
):
    sample = _get_sample_for_api(sample_id, user)
    form_data = payload.form_data
    doc = create_comment_doc(form_data, key="sample_comment")
    repository.add_sample_comment(sample_id, doc)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id="new", action="add")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/samples/{sample_id}/comments", response_model=SampleMutationPayload, status_code=201, summary="Create sample comment")
def create_sample_comment(
    sample_id: str,
    payload: SampleCommentCreateRequest,
    user: ApiUser = Depends(require_access(permission="add_sample_comment", min_role="user", min_level=9)),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    return _add_sample_comment(sample_id=sample_id, payload=payload, user=user, repository=repository)


def _hide_sample_comment(sample_id: str, comment_id: str, user: ApiUser, repository: SamplesRepository):
    sample = _get_sample_for_api(sample_id, user)
    repository.hide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="hide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.patch("/api/v1/samples/{sample_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Hide sample comment")
def hide_sample_comment(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_sample_comment", min_role="manager", min_level=99)),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    return _hide_sample_comment(sample_id=sample_id, comment_id=comment_id, user=user, repository=repository)


def _unhide_sample_comment(sample_id: str, comment_id: str, user: ApiUser, repository: SamplesRepository):
    sample = _get_sample_for_api(sample_id, user)
    repository.unhide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="unhide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.delete("/api/v1/samples/{sample_id}/comments/{comment_id}/hidden", response_model=SampleMutationPayload, summary="Unhide sample comment")
def unhide_sample_comment(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_sample_comment", min_role="manager", min_level=99)),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    return _unhide_sample_comment(sample_id=sample_id, comment_id=comment_id, user=user, repository=repository)


def _update_sample_filters(
    sample_id: str,
    payload: SampleFiltersUpdateRequest,
    user: ApiUser,
    repository: SamplesRepository,
):
    sample = _get_sample_for_api(sample_id, user)
    filters = payload.filters
    normalized_filters = dict(filters)
    existing_filters = dict(sample.get("filters") or {})
    if "adhoc_genes" not in normalized_filters and "adhoc_genes" in existing_filters:
        normalized_filters["adhoc_genes"] = existing_filters.get("adhoc_genes")

    if str(sample.get("omics_layer", "")).lower() == "rna":
        normalized_filters = normalize_rna_filter_keys(normalized_filters)
        normalized_filters["fusion_callers"] = create_fusioncallers(normalized_filters.get("fusion_callers", []))
        normalized_filters["fusion_effects"] = create_fusioneffectlist(normalized_filters.get("fusion_effects", []))
        fusionlists = normalized_filters.get("fusionlists")
        if fusionlists is None:
            normalized_filters["fusionlists"] = []
        elif isinstance(fusionlists, str):
            normalized_filters["fusionlists"] = [fusionlists] if fusionlists else []
        elif isinstance(fusionlists, tuple):
            normalized_filters["fusionlists"] = list(fusionlists)
        normalized_filters["fusionlists"] = list(dict.fromkeys(normalized_filters.get("fusionlists", [])))
    else:
        normalized_filters = normalize_dna_filter_keys(normalized_filters)

    repository.update_sample_filters(sample.get("_id"), normalized_filters)
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="update")
    return util.common.convert_to_serializable(result)


@router.put("/api/v1/samples/{sample_id}/filters", response_model=SampleMutationPayload, summary="Replace sample filters")
def update_sample_filters(
    sample_id: str,
    payload: SampleFiltersUpdateRequest,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    return _update_sample_filters(sample_id=sample_id, payload=payload, user=user, repository=repository)


def _reset_sample_filters(sample_id: str, user: ApiUser, repository: SamplesRepository):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = get_formatted_assay_config(sample)
    if not assay_config:
        raise api_error(404, "Assay config not found for sample")
    repository.reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="reset")
    return util.common.convert_to_serializable(result)


@router.delete("/api/v1/samples/{sample_id}/filters", response_model=SampleMutationPayload, summary="Reset sample filters")
def reset_sample_filters(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    return _reset_sample_filters(sample_id=sample_id, user=user, repository=repository)


def _update_coverage_blacklist(payload: CoverageBlacklistUpdateRequest, repository: SamplesRepository):
    gene = payload.gene
    coord = payload.coord or ""
    smp_grp = payload.smp_grp
    region = payload.region
    status = payload.status
    if coord:
        coord = str(coord).replace(":", "_").replace("-", "_")
        repository.blacklist_coord(gene, coord, region, smp_grp)
        return util.common.convert_to_serializable(
            {
                "status": "ok",
                "message": (
                    f" Status for {gene}:{region}:{coord} was set as {status} for group: {smp_grp}. "
                    "Page needs to be reload to take effect"
                ),
            }
        )
    repository.blacklist_gene(gene, smp_grp)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "message": (
                f" Status for full gene: {gene} was set as {status} for group: {smp_grp}. "
                "Page needs to be reload to take effect"
            ),
        }
    )


@router.post("/api/v1/coverage/blacklist/entries", response_model=CoverageBlacklistStatusPayload, summary="Create coverage blacklist entry")
def create_coverage_blacklist_entry(
    payload: CoverageBlacklistUpdateRequest,
    user: ApiUser = Depends(require_access(min_level=1)),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    _ = user
    return _update_coverage_blacklist(payload=payload, repository=repository)


def _remove_coverage_blacklist(obj_id: str, repository: SamplesRepository):
    repository.remove_blacklist(obj_id)
    return util.common.convert_to_serializable(
        _mutation_payload("coverage", resource="blacklist", resource_id=obj_id, action="remove")
    )


@router.delete("/api/v1/coverage/blacklist/entries/{obj_id}", response_model=SampleMutationPayload, summary="Delete coverage blacklist entry")
def delete_coverage_blacklist_entry(
    obj_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    repository: SamplesRepository = Depends(get_sample_repository),
):
    _ = user
    return _remove_coverage_blacklist(obj_id=obj_id, repository=repository)

