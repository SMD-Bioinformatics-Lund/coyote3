"""Sample and coverage mutation router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.core.interpretation.report_summary import create_comment_doc
from api.core.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.core.samples.ports import SamplesRepository
from api.core.workflows.filter_normalization import normalize_dna_filter_keys, normalize_rna_filter_keys
from api.contracts.home import (
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeMutationStatusPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
)
from api.deps.repositories import get_sample_repository
from api.deps.services import get_sample_catalog_service
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
from api.services.sample_catalog_service import SampleCatalogService

router = APIRouter(tags=["samples"])

if not hasattr(util, "common"):
    util.init_util()


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    """Handle  mutation payload.

    Args:
            sample_id: Sample id.
            resource: Resource.
            resource_id: Resource id.
            action: Action.

    Returns:
            The  mutation payload result.
    """
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@router.get("/api/v1/samples", response_model=HomeSamplesPayload)
def list_samples_read(
    status: str = "live",
    search_str: str = "",
    search_mode: str = "live",
    sample_view: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    live_page: int = Query(default=1, ge=1),
    done_page: int = Query(default=1, ge=1),
    live_per_page: int | None = Query(default=None, ge=1, le=200),
    done_per_page: int | None = Query(default=None, ge=1, le=200),
    profile_scope: str = Query(default="production"),
    panel_type: str | None = None,
    panel_tech: str | None = None,
    assay_group: str | None = None,
    limit_done_samples: int | None = None,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """List samples read.

    Args:
        status (str): Value for ``status``.
        search_str (str): Value for ``search_str``.
        search_mode (str): Value for ``search_mode``.
        sample_view (str | None): Value for ``sample_view``.
        page (int): Value for ``page``.
        per_page (int): Value for ``per_page``.
        live_page (int): Value for ``live_page``.
        done_page (int): Value for ``done_page``.
        live_per_page (int | None): Value for ``live_per_page``.
        done_per_page (int | None): Value for ``done_per_page``.
        profile_scope (str): Value for ``profile_scope``.
        panel_type (str | None): Value for ``panel_type``.
        panel_tech (str | None): Value for ``panel_tech``.
        assay_group (str | None): Value for ``assay_group``.
        limit_done_samples (int | None): Value for ``limit_done_samples``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = sample_view
    live_per_page = live_per_page or per_page
    done_per_page = done_per_page or per_page
    return util.common.convert_to_serializable(
        service.samples_payload(
            user=user,
            status=status,
            search_str=search_str,
            search_mode=search_mode,
            page=page,
            per_page=per_page,
            live_page=live_page,
            per_live_page=live_per_page,
            done_page=done_page,
            per_done_page=done_per_page,
            profile_scope=profile_scope,
            panel_type=panel_type,
            panel_tech=panel_tech,
            assay_group=assay_group,
            limit_done_samples=limit_done_samples,
        )
    )


@router.get("/api/v1/samples/{sample_id}/genelists", response_model=HomeItemsPayload)
def sample_genelists_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample genelists read.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.genelist_items_payload(sample=sample))


@router.get("/api/v1/samples/{sample_id}/effective-genes", response_model=HomeEffectiveGenesPayload)
def sample_effective_genes_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample effective genes read.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.effective_genes_payload(sample=sample))


@router.get("/api/v1/samples/{sample_id}/edit-context", response_model=HomeEditContextPayload)
def sample_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample edit context read.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.edit_context_payload(sample=sample))


@router.put("/api/v1/samples/{sample_id}/genelists/selection", response_model=HomeMutationStatusPayload)
def sample_apply_genelists_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample apply genelists mutation.

    Args:
        sample_id (str): Value for ``sample_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.apply_genelists(sample=sample, payload=payload, sample_id=sample_id))


@router.put("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeMutationStatusPayload)
def sample_save_adhoc_genes_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample save adhoc genes mutation.

    Args:
        sample_id (str): Value for ``sample_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.save_adhoc_genes(sample=sample, payload=payload, sample_id=sample_id)
    )


@router.delete("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeMutationStatusPayload)
def sample_clear_adhoc_genes_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample clear adhoc genes mutation.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.clear_adhoc_genes(sample=sample, sample_id=sample_id))


@router.get("/api/v1/samples/{sample_id}/reports/{report_id}/context", response_model=HomeReportContextPayload)
def sample_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="view_reports", min_role="admin")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Handle sample report context read.

    Args:
        sample_id (str): Value for ``sample_id``.
        report_id (str): Value for ``report_id``.
        user (ApiUser): Value for ``user``.
        service (SampleCatalogService): Value for ``service``.

    Returns:
        The function result.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.report_context_payload(sample=sample, report_id=report_id, sample_id=sample_id)
    )


def _add_sample_comment(
    sample_id: str,
    payload: SampleCommentCreateRequest,
    user: ApiUser,
    repository: SamplesRepository,
):
    """Handle  add sample comment.

    Args:
            sample_id: Sample id.
            payload: Payload.
            user: User.
            repository: Repository.

    Returns:
            The  add sample comment result.
    """
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
    """Create sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        payload (SampleCommentCreateRequest): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    return _add_sample_comment(sample_id=sample_id, payload=payload, user=user, repository=repository)


def _hide_sample_comment(sample_id: str, comment_id: str, user: ApiUser, repository: SamplesRepository):
    """Handle  hide sample comment.

    Args:
            sample_id: Sample id.
            comment_id: Comment id.
            user: User.
            repository: Repository.

    Returns:
            The  hide sample comment result.
    """
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
    """Handle hide sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        comment_id (str): Value for ``comment_id``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    return _hide_sample_comment(sample_id=sample_id, comment_id=comment_id, user=user, repository=repository)


def _unhide_sample_comment(sample_id: str, comment_id: str, user: ApiUser, repository: SamplesRepository):
    """Handle  unhide sample comment.

    Args:
            sample_id: Sample id.
            comment_id: Comment id.
            user: User.
            repository: Repository.

    Returns:
            The  unhide sample comment result.
    """
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
    """Handle unhide sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        comment_id (str): Value for ``comment_id``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    return _unhide_sample_comment(sample_id=sample_id, comment_id=comment_id, user=user, repository=repository)


def _update_sample_filters(
    sample_id: str,
    payload: SampleFiltersUpdateRequest,
    user: ApiUser,
    repository: SamplesRepository,
):
    """Handle  update sample filters.

    Args:
            sample_id: Sample id.
            payload: Payload.
            user: User.
            repository: Repository.

    Returns:
            The  update sample filters result.
    """
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
    """Update sample filters.

    Args:
        sample_id (str): Value for ``sample_id``.
        payload (SampleFiltersUpdateRequest): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    return _update_sample_filters(sample_id=sample_id, payload=payload, user=user, repository=repository)


def _reset_sample_filters(sample_id: str, user: ApiUser, repository: SamplesRepository):
    """Handle  reset sample filters.

    Args:
            sample_id: Sample id.
            user: User.
            repository: Repository.

    Returns:
            The  reset sample filters result.
    """
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
    """Reset sample filters.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    return _reset_sample_filters(sample_id=sample_id, user=user, repository=repository)


def _update_coverage_blacklist(payload: CoverageBlacklistUpdateRequest, repository: SamplesRepository):
    """Handle  update coverage blacklist.

    Args:
            payload: Payload.
            repository: Repository.

    Returns:
            The  update coverage blacklist result.
    """
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
    """Create coverage blacklist entry.

    Args:
        payload (CoverageBlacklistUpdateRequest): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _ = user
    return _update_coverage_blacklist(payload=payload, repository=repository)


def _remove_coverage_blacklist(obj_id: str, repository: SamplesRepository):
    """Handle  remove coverage blacklist.

    Args:
            obj_id: Obj id.
            repository: Repository.

    Returns:
            The  remove coverage blacklist result.
    """
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
    """Delete coverage blacklist entry.

    Args:
        obj_id (str): Value for ``obj_id``.
        user (ApiUser): Value for ``user``.
        repository (SamplesRepository): Value for ``repository``.

    Returns:
        The function result.
    """
    _ = user
    return _remove_coverage_blacklist(obj_id=obj_id, repository=repository)
