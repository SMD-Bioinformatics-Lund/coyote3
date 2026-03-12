"""Canonical home router module."""

from __future__ import annotations

import re
from copy import deepcopy

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.home import (
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeMutationStatusPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
)
from api.core.home.ports import HomeRepository
from api.extensions import store, util
from api.http import api_error as _api_error, get_formatted_assay_config as _get_formatted_assay_config
from api.repositories.home_repository import HomeRepository as MongoHomeRepository
from api.runtime import app as runtime_app
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["home"])

_home_repo_instance: HomeRepository | None = None

if not hasattr(util, "common"):
    util.init_util()


def _home_repo() -> HomeRepository:
    global _home_repo_instance
    from api.infra.repositories import home_mongo

    home_mongo.store = store
    if _home_repo_instance is None:
        _home_repo_instance = MongoHomeRepository()
    return _home_repo_instance


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
):
    if limit_done_samples is None:
        limit_done_samples = runtime_app.config.get("REPORTED_SAMPLES_SEARCH_LIMIT", 50)

    if panel_type and panel_tech and assay_group:
        assay_list = user.asp_map.get(panel_type, {}).get(panel_tech, {}).get(assay_group, [])
        accessible_assays = [a for a in assay_list if a in user.assays]
    else:
        accessible_assays = user.assays

    normalized_scope = (profile_scope or "").strip().lower()
    use_all_profiles = normalized_scope == "all"
    query_envs = list(user.envs)
    if not use_all_profiles:
        query_envs = ["production"] if "production" in user.envs else list(user.envs)

    live_per_page = live_per_page or per_page
    done_per_page = done_per_page or per_page
    live_offset = max(0, (live_page - 1) * live_per_page)
    done_offset = max(0, (done_page - 1) * done_per_page)
    live_fetch_limit = live_per_page + 1
    done_fetch_limit = done_per_page + 1
    search_applied = bool((search_str or "").strip())

    done_samples: list[dict] = []
    live_samples: list[dict] = []
    has_next_live = False
    has_next_done = False

    done_limit = None if search_applied else done_fetch_limit
    if not search_applied and limit_done_samples:
        done_limit = min(done_fetch_limit, limit_done_samples + 1)
    done_samples = _home_repo().get_samples(
        user_assays=accessible_assays,
        user_envs=query_envs,
        status="done",
        search_str=search_str,
        report=True,
        limit=done_limit,
        offset=0 if search_applied else done_offset,
        use_cache=True,
        reload=False,
    )
    if not search_applied and len(done_samples) > done_per_page:
        has_next_done = True
        done_samples = done_samples[:done_per_page]

    live_samples = _home_repo().get_samples(
        user_assays=accessible_assays,
        status="live",
        user_envs=query_envs,
        search_str=search_str,
        report=False,
        limit=None if search_applied else live_fetch_limit,
        offset=0 if search_applied else live_offset,
        use_cache=True,
        reload=False,
    )
    if not search_applied and len(live_samples) > live_per_page:
        has_next_live = True
        live_samples = live_samples[:live_per_page]

    for sample in done_samples:
        sample["last_report_time_created"] = (
            sample["reports"][-1]["time_created"]
            if sample.get("reports") and sample["reports"][-1].get("time_created")
            else 0
        )

    return util.common.convert_to_serializable(
        {
            "live_samples": live_samples,
            "done_samples": done_samples,
            "status": status,
            "search_mode": search_mode,
            "sample_view": "all",
            "profile_scope": "all" if use_all_profiles else "production",
            "page": page,
            "per_page": per_page,
            "live_page": live_page,
            "live_per_page": live_per_page,
            "done_page": done_page,
            "done_per_page": done_per_page,
            "has_next_live": has_next_live,
            "has_next_done": has_next_done,
            "panel_type": panel_type,
            "panel_tech": panel_tech,
            "assay_group": assay_group,
        }
    )


@router.get("/api/v1/home/samples/{sample_id}/isgls", response_model=HomeItemsPayload)
def home_isgls_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    sample = _get_sample_for_api(sample_id, user)
    query = {"asp_name": sample.get("assay"), "is_active": True}
    isgls = _home_repo().get_isgl_by_asp(**query)
    items = [
        {
            "_id": str(gl["_id"]),
            "name": gl["displayname"],
            "version": gl.get("version"),
            "adhoc": gl.get("adhoc", False),
            "gene_count": int(gl.get("gene_count") or 0),
        }
        for gl in isgls
    ]
    return util.common.convert_to_serializable({"items": items})


@router.get("/api/v1/home/samples/{sample_id}/effective_genes/all", response_model=HomeEffectiveGenesPayload)
def home_effective_genes_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = sample.get("filters", {})
    assay = sample.get("assay")
    asp = _home_repo().get_asp(assay)
    asp_group = asp.get("asp_group")
    asp_covered_genes, _asp_germline_genes = _home_repo().get_asp_genes(assay)

    effective_genes = set(asp_covered_genes)
    adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
    isgl_genes: set[str] = set()

    genelists = filters.get("genelists", [])
    if genelists:
        isgls = _home_repo().get_isgl_by_ids(genelists)
        for _gl_key, gl_values in isgls.items():
            isgl_genes.update(gl_values.get("genes", []))

    filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()
    if filter_genes and asp_group not in ["tumwgs", "wts"]:
        effective_genes = effective_genes.intersection(filter_genes)
    elif filter_genes:
        effective_genes = deepcopy(filter_genes)

    items = sorted(effective_genes)
    return util.common.convert_to_serializable({"items": items, "asp_covered_genes_count": len(asp_covered_genes)})


@router.get("/api/v1/home/samples/{sample_id}/edit_context", response_model=HomeEditContextPayload)
def home_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    asp = _home_repo().get_asp(sample.get("assay"))
    asp_group = asp.get("asp_group")

    if sample.get("filters") is None:
        assay_config = _get_formatted_assay_config(sample)
        _home_repo().reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
        sample = _home_repo().get_sample(sample_id)

    filters = sample.get("filters", {})
    assay = sample.get("assay")
    asp_covered_genes, _asp_germline_genes = _home_repo().get_asp_genes(assay)
    effective_genes = set(asp_covered_genes)

    adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
    isgl_genes: set[str] = set()
    genelists = filters.get("genelists", [])
    if genelists:
        isgls = _home_repo().get_isgl_by_ids(genelists)
        for _gl_key, gl_values in isgls.items():
            isgl_genes.update(gl_values.get("genes", []))
    filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()

    if filter_genes and asp_group not in ["tumwgs", "wts"]:
        effective_genes = effective_genes.intersection(filter_genes)
    elif filter_genes:
        effective_genes = deepcopy(filter_genes)
    effective_genes = sorted(effective_genes)

    variant_stats_raw = _home_repo().get_variant_stats(str(sample.get("_id")))
    if effective_genes and variant_stats_raw and (len(effective_genes) < len(asp_covered_genes) or asp_group in ["tumwgs", "wts"]):
        variant_stats_filtered = _home_repo().get_variant_stats(str(sample.get("_id")), genes=effective_genes)
    else:
        variant_stats_filtered = deepcopy(variant_stats_raw)

    return util.common.convert_to_serializable(
        {
            "sample": sample,
            "asp": asp,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
        }
    )


@router.post("/api/v1/home/samples/{sample_id}/genes/apply-isgl", response_model=HomeMutationStatusPayload)
def home_apply_isgl_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = sample.get("filters", {})
    isgl_ids = payload.get("isgl_ids", [])
    if not isinstance(isgl_ids, list):
        raise _api_error(400, "Invalid isgl_ids payload")
    filters["genelists"] = list(deepcopy(isgl_ids))
    _home_repo().update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable({"status": "ok", "sample_id": sample_id, "action": "apply_isgl", "isgl_ids": isgl_ids})


@router.post("/api/v1/home/samples/{sample_id}/adhoc_genes/save", response_model=HomeMutationStatusPayload)
def home_save_adhoc_genes_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    genes_raw = payload.get("genes", "")
    genes = [g.strip() for g in re.split(r"[ ,\n]+", genes_raw) if g.strip()]
    genes.sort()
    label = payload.get("label") or "adhoc"

    filters = sample.get("filters", {})
    filters["adhoc_genes"] = {"label": label, "genes": genes}
    _home_repo().update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable(
        {"status": "ok", "sample_id": sample_id, "action": "save_adhoc_genes", "label": label, "gene_count": len(genes)}
    )


@router.post("/api/v1/home/samples/{sample_id}/adhoc_genes/clear", response_model=HomeMutationStatusPayload)
def home_clear_adhoc_genes_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = sample.get("filters", {})
    filters.pop("adhoc_genes", None)
    _home_repo().update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable({"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"})


@router.get("/api/v1/home/samples/{sample_id}/reports/{report_id}/context", response_model=HomeReportContextPayload)
def home_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="view_reports", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    report = _home_repo().get_report(sample_id, report_id)
    report_name = report.get("report_name")
    filepath = report.get("filepath")

    if not filepath and report_name:
        assay_config = _get_formatted_assay_config(sample)
        report_sub_dir = assay_config.get("reporting", {}).get("report_folder", "")
        filepath = f"{runtime_app.config.get('REPORTS_BASE_PATH', '')}/{report_sub_dir}/{report_name}"

    return util.common.convert_to_serializable(
        {"sample_id": sample_id, "report_id": report_id, "report_name": report_name, "filepath": filepath}
    )
