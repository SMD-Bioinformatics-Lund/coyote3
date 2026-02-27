"""Sample and coverage mutation routes."""

from fastapi import Body, Depends

from api.extensions import store, util
from api.services.interpretation.report_summary import create_comment_doc
from api.services.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.services.workflow.filter_normalization import normalize_rna_filter_keys
from api.app import ApiUser, _api_error, _get_formatted_assay_config, _get_sample_for_api, app, require_access


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@app.post("/api/v1/samples/{sample_id}/sample_comments/add")
def add_sample_comment_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="add_sample_comment", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    form_data = payload.get("form_data", {})
    doc = create_comment_doc(form_data, key="sample_comment")
    store.sample_handler.add_sample_comment(sample_id, doc)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id="new", action="add")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/sample_comments/{comment_id}/hide")
def hide_sample_comment_mutation(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_sample_comment", min_role="manager", min_level=99)),
):
    sample = _get_sample_for_api(sample_id, user)
    store.sample_handler.hide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="hide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/sample_comments/{comment_id}/unhide")
def unhide_sample_comment_mutation(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_sample_comment", min_role="manager", min_level=99)),
):
    sample = _get_sample_for_api(sample_id, user)
    store.sample_handler.unhide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="unhide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/filters/update")
def update_sample_filters_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    filters = payload.get("filters", {})
    if not isinstance(filters, dict):
        raise _api_error(400, "Invalid filters payload")
    normalized_filters = dict(filters)

    if str(sample.get("omics_layer", "")).lower() == "rna":
        normalized_filters = normalize_rna_filter_keys(normalized_filters)
        normalized_filters["fusion_callers"] = create_fusioncallers(
            normalized_filters.get("fusion_callers", [])
        )
        normalized_filters["fusion_effects"] = create_fusioneffectlist(
            normalized_filters.get("fusion_effects", [])
        )

        fusionlists = normalized_filters.get("fusionlists")
        if fusionlists is None:
            normalized_filters["fusionlists"] = []
        elif isinstance(fusionlists, str):
            normalized_filters["fusionlists"] = [fusionlists] if fusionlists else []
        elif isinstance(fusionlists, tuple):
            normalized_filters["fusionlists"] = list(fusionlists)

        normalized_filters["fusionlists"] = list(dict.fromkeys(normalized_filters.get("fusionlists", [])))

    store.sample_handler.update_sample_filters(sample.get("_id"), normalized_filters)
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="update")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/filters/reset")
def reset_sample_filters_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    store.sample_handler.reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="reset")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/coverage/blacklist/update")
def update_coverage_blacklist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    gene = payload.get("gene")
    coord = payload.get("coord", "")
    smp_grp = payload.get("smp_grp")
    region = payload.get("region")
    if coord:
        coord = str(coord).replace(":", "_").replace("-", "_")
        store.groupcov_handler.blacklist_coord(gene, coord, region, smp_grp)
        return util.common.convert_to_serializable(
            {
                "status": "ok",
                "message": (
                    f" Status for {gene}:{region}:{coord} was set as {payload.get('status')} for group: {smp_grp}. "
                    "Page needs to be reload to take effect"
                ),
            }
        )
    store.groupcov_handler.blacklist_gene(gene, smp_grp)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "message": (
                f" Status for full gene: {gene} was set as {payload.get('status')} for group: {smp_grp}. "
                "Page needs to be reload to take effect"
            ),
        }
    )


@app.post("/api/v1/coverage/blacklist/{obj_id}/remove")
def remove_coverage_blacklist_mutation(
    obj_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    store.groupcov_handler.remove_blacklist(obj_id)
    return util.common.convert_to_serializable(
        _mutation_payload("coverage", resource="blacklist", resource_id=obj_id, action="remove")
    )
