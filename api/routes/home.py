"""Home/read routes backing Flask home blueprint pages."""

from __future__ import annotations

from copy import deepcopy
import re

from fastapi import Body, Depends, Query

from api.app import (
    ApiUser,
    _api_error,
    _get_formatted_assay_config,
    _get_sample_for_api,
    flask_app,
    app,
    require_access,
)
from coyote.extensions import store, util


@app.get("/api/v1/home/samples")
def home_samples_read(
    status: str = "live",
    search_str: str = "",
    search_mode: str = "live",
    panel_type: str | None = None,
    panel_tech: str | None = None,
    assay_group: str | None = None,
    limit_done_samples: int | None = None,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    if limit_done_samples is None:
        limit_done_samples = flask_app.config.get("REPORTED_SAMPLES_SEARCH_LIMIT", 50)

    if panel_type and panel_tech and assay_group:
        assay_list = user.asp_map.get(panel_type, {}).get(panel_tech, {}).get(assay_group, [])
        accessible_assays = [a for a in assay_list if a in user.assays]
    else:
        accessible_assays = user.assays

    time_limit = None if search_str else util.common.get_date_days_ago(days=90)

    done_samples: list[dict] = []
    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            user_envs=user.envs,
            status=status,
            search_str=search_str,
            report=True,
            limit=limit_done_samples,
            use_cache=True,
            reload=False,
        )

    live_samples: list[dict] = []
    if status == "live" or search_mode in ["live", "both"]:
        live_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            status=status,
            user_envs=user.envs,
            search_str=search_str,
            report=False,
            use_cache=True,
            reload=False,
        )

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
            "panel_type": panel_type,
            "panel_tech": panel_tech,
            "assay_group": assay_group,
        }
    )


@app.get("/api/v1/home/samples/{sample_id}/isgls")
def home_isgls_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    sample = _get_sample_for_api(sample_id, user)
    query = {"asp_name": sample.get("assay"), "is_active": True}
    isgls = store.isgl_handler.get_isgl_by_asp(**query)
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


@app.get("/api/v1/home/samples/{sample_id}/effective_genes/all")
def home_effective_genes_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = sample.get("filters", {})
    assay = sample.get("assay")
    asp = store.asp_handler.get_asp(assay)
    asp_group = asp.get("asp_group")
    asp_covered_genes, _asp_germline_genes = store.asp_handler.get_asp_genes(assay)

    effective_genes = set(asp_covered_genes)
    adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
    isgl_genes: set[str] = set()

    genelists = filters.get("genelists", [])
    if genelists:
        isgls = store.isgl_handler.get_isgl_by_ids(genelists)
        for _gl_key, gl_values in isgls.items():
            isgl_genes.update(gl_values.get("genes", []))

    filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()
    if filter_genes and asp_group not in ["tumwgs", "wts"]:
        effective_genes = effective_genes.intersection(filter_genes)
    elif filter_genes:
        effective_genes = deepcopy(filter_genes)

    items = sorted(effective_genes)
    return util.common.convert_to_serializable(
        {"items": items, "asp_covered_genes_count": len(asp_covered_genes)}
    )


@app.get("/api/v1/home/samples/{sample_id}/edit_context")
def home_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    asp = store.asp_handler.get_asp(sample.get("assay"))
    asp_group = asp.get("asp_group")

    if sample.get("filters") is None:
        assay_config = _get_formatted_assay_config(sample)
        store.sample_handler.reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
        sample = store.sample_handler.get_sample(sample_id)

    filters = sample.get("filters", {})
    assay = sample.get("assay")
    asp_covered_genes, _asp_germline_genes = store.asp_handler.get_asp_genes(assay)
    effective_genes = set(asp_covered_genes)

    adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
    isgl_genes: set[str] = set()
    genelists = filters.get("genelists", [])
    if genelists:
        isgls = store.isgl_handler.get_isgl_by_ids(genelists)
        for _gl_key, gl_values in isgls.items():
            isgl_genes.update(gl_values.get("genes", []))
    filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()

    if filter_genes and asp_group not in ["tumwgs", "wts"]:
        effective_genes = effective_genes.intersection(filter_genes)
    elif filter_genes:
        effective_genes = deepcopy(filter_genes)
    effective_genes = sorted(effective_genes)

    variant_stats_raw = store.variant_handler.get_variant_stats(str(sample.get("_id")))
    if (
        effective_genes
        and variant_stats_raw
        and (len(effective_genes) < len(asp_covered_genes) or asp_group in ["tumwgs", "wts"])
    ):
        variant_stats_filtered = store.variant_handler.get_variant_stats(
            str(sample.get("_id")), genes=effective_genes
        )
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


@app.post("/api/v1/home/samples/{sample_id}/genes/apply-isgl")
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
    store.sample_handler.update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable(
        {"status": "ok", "sample_id": sample_id, "action": "apply_isgl", "isgl_ids": isgl_ids}
    )


@app.post("/api/v1/home/samples/{sample_id}/adhoc_genes/save")
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
    store.sample_handler.update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "sample_id": sample_id,
            "action": "save_adhoc_genes",
            "label": label,
            "gene_count": len(genes),
        }
    )


@app.post("/api/v1/home/samples/{sample_id}/adhoc_genes/clear")
def home_clear_adhoc_genes_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = sample.get("filters", {})
    filters.pop("adhoc_genes", None)
    store.sample_handler.update_sample_filters(sample.get("_id"), filters)
    return util.common.convert_to_serializable(
        {"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"}
    )
