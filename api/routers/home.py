"""Canonical home router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.home import (
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeMutationStatusPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
)
from api.deps.services import get_home_service
from api.extensions import util
from api.runtime import app as runtime_app
from api.services.home_service import HomeService
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["home"])

if not hasattr(util, "common"):
    util.init_util()


@router.get("/api/v1/home/samples", response_model=HomeSamplesPayload)
def home_samples_read(
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
    service: HomeService = Depends(get_home_service),
):
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


@router.get("/api/v1/home/samples/{sample_id}/isgls", response_model=HomeItemsPayload)
def home_isgls_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.isgl_items_payload(sample=sample))


@router.get("/api/v1/home/samples/{sample_id}/effective_genes/all", response_model=HomeEffectiveGenesPayload)
def home_effective_genes_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.effective_genes_payload(sample=sample))


@router.get("/api/v1/home/samples/{sample_id}/edit_context", response_model=HomeEditContextPayload)
def home_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.edit_context_payload(sample=sample))


@router.post("/api/v1/home/samples/{sample_id}/genes/apply-isgl", response_model=HomeMutationStatusPayload)
def home_apply_isgl_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.apply_isgl(sample=sample, payload=payload, sample_id=sample_id))


@router.post("/api/v1/home/samples/{sample_id}/adhoc_genes/save", response_model=HomeMutationStatusPayload)
def home_save_adhoc_genes_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.save_adhoc_genes(sample=sample, payload=payload, sample_id=sample_id)
    )


@router.post("/api/v1/home/samples/{sample_id}/adhoc_genes/clear", response_model=HomeMutationStatusPayload)
def home_clear_adhoc_genes_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.clear_adhoc_genes(sample=sample, sample_id=sample_id))


@router.get("/api/v1/home/samples/{sample_id}/reports/{report_id}/context", response_model=HomeReportContextPayload)
def home_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="view_reports", min_role="admin")),
    service: HomeService = Depends(get_home_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.report_context_payload(sample=sample, report_id=report_id, sample_id=sample_id)
    )
