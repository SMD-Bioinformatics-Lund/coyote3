"""Coverage read routes for Flask presentation endpoints."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from fastapi import Depends, Query

from api.app import ApiUser, _api_error, _get_sample_for_api, app, require_access
from api.services.coverage_processing import CoverageProcessingService
from api.extensions import store, util


@app.get("/api/v1/coverage/samples/{sample_id}")
def coverage_sample_read(
    sample_id: str,
    cov_cutoff: int = Query(default=500, ge=1),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    sample = _get_sample_for_api(sample_id, user)
    sample_assay = sample.get("assay", "unknown")
    sample_profile = sample.get("profile", "production")
    assay_config = store.aspc_handler.get_aspc_no_meta(sample_assay, sample_profile)
    if not assay_config:
        raise _api_error(404, "Assay config not found")

    assay_group = assay_config.get("assay_group", "unknown")
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)
    sample_filters = sample.get("filters", {})
    checked_genelists = sample_filters.get("genelists", [])

    if checked_genelists:
        checked_genelists_genes_dict = store.isgl_handler.get_isgl_by_ids(checked_genelists)
        _genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
            sample,
            assay_panel_doc,
            checked_genelists_genes_dict,
        )
    else:
        checked_genelists = [assay_panel_doc.get("_id")]
        filter_genes = assay_panel_doc.get("covered_genes", [])

    cov_dict = store.coverage2_handler.get_sample_coverage(str(sample["_id"])) or {}
    cov_dict = deepcopy(cov_dict)
    cov_dict.pop("_id", None)
    sample_payload = deepcopy(sample)
    sample_payload.pop("_id", None)

    filtered_dict = CoverageProcessingService.filter_genes_from_form(cov_dict, filter_genes, assay_group)
    filtered_dict = CoverageProcessingService.find_low_covered_genes(filtered_dict, cov_cutoff, assay_group)
    cov_table = CoverageProcessingService.coverage_table(filtered_dict, cov_cutoff)
    filtered_dict = CoverageProcessingService.organize_data_for_d3(filtered_dict)

    return util.common.convert_to_serializable(
        {
            "coverage": filtered_dict,
            "cov_cutoff": cov_cutoff,
            "sample": sample_payload,
            "genelists": checked_genelists,
            "smp_grp": assay_group,
            "cov_table": cov_table,
        }
    )


@app.get("/api/v1/coverage/blacklisted/{group}")
def coverage_blacklisted_read(
    group: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    if group not in set(user.assay_groups or []):
        raise _api_error(403, "Access denied: You do not belong to the target assay.")

    grouped_by_gene = defaultdict(dict)
    blacklisted = store.groupcov_handler.get_regions_per_group(group)
    for entry in blacklisted:
        if entry["region"] == "gene":
            grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
        elif entry["region"] == "CDS":
            grouped_by_gene[entry["gene"]]["CDS"] = entry
        elif entry["region"] == "probe":
            grouped_by_gene[entry["gene"]]["probe"] = entry

    return util.common.convert_to_serializable({"blacklisted": grouped_by_gene, "group": group})
