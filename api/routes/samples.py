"""Sample and coverage mutation routes."""

from fastapi import Body, Depends

from api.core.samples.ports import SamplesRepository
from api.contracts.samples import CoverageBlacklistStatusPayload, SampleMutationPayload
from api.extensions import util
from api.core.interpretation.report_summary import create_comment_doc
from api.core.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.core.workflows.filter_normalization import normalize_dna_filter_keys, normalize_rna_filter_keys
from api.app import _api_error, _get_formatted_assay_config, app
from api.infra.repositories.samples_mongo import MongoSamplesRepository
from api.security.access import ApiUser, _get_sample_for_api, require_access


_samples_repo_instance: SamplesRepository | None = None


def _samples_repo() -> SamplesRepository:
    global _samples_repo_instance
    if _samples_repo_instance is None:
        _samples_repo_instance = MongoSamplesRepository()
    return _samples_repo_instance


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@app.post("/api/v1/samples/{sample_id}/sample_comments/add", response_model=SampleMutationPayload)
def add_sample_comment_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="add_sample_comment", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    form_data = payload.get("form_data", {})
    doc = create_comment_doc(form_data, key="sample_comment")
    _samples_repo().add_sample_comment(sample_id, doc)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id="new", action="add")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/sample_comments/{comment_id}/hide", response_model=SampleMutationPayload)
def hide_sample_comment_mutation(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_sample_comment", min_role="manager", min_level=99)),
):
    sample = _get_sample_for_api(sample_id, user)
    _samples_repo().hide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="hide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post(
    "/api/v1/samples/{sample_id}/sample_comments/{comment_id}/unhide",
    response_model=SampleMutationPayload,
)
def unhide_sample_comment_mutation(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_sample_comment", min_role="manager", min_level=99)),
):
    sample = _get_sample_for_api(sample_id, user)
    _samples_repo().unhide_sample_comment(sample_id, comment_id)
    result = _mutation_payload(sample_id, resource="sample_comment", resource_id=comment_id, action="unhide")
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/filters/update", response_model=SampleMutationPayload)
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
    existing_filters = dict(sample.get("filters") or {})
    if "adhoc_genes" not in normalized_filters and "adhoc_genes" in existing_filters:
        normalized_filters["adhoc_genes"] = existing_filters.get("adhoc_genes")

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
    else:
        normalized_filters = normalize_dna_filter_keys(normalized_filters)

    _samples_repo().update_sample_filters(sample.get("_id"), normalized_filters)
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="update")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/samples/{sample_id}/filters/reset", response_model=SampleMutationPayload)
def reset_sample_filters_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    _samples_repo().reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
    result = _mutation_payload(sample_id, resource="sample_filters", resource_id=str(sample.get("_id")), action="reset")
    return util.common.convert_to_serializable(result)


@app.post("/api/v1/coverage/blacklist/update", response_model=CoverageBlacklistStatusPayload)
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
        _samples_repo().blacklist_coord(gene, coord, region, smp_grp)
        return util.common.convert_to_serializable(
            {
                "status": "ok",
                "message": (
                    f" Status for {gene}:{region}:{coord} was set as {payload.get('status')} for group: {smp_grp}. "
                    "Page needs to be reload to take effect"
                ),
            }
        )
    _samples_repo().blacklist_gene(gene, smp_grp)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "message": (
                f" Status for full gene: {gene} was set as {payload.get('status')} for group: {smp_grp}. "
                "Page needs to be reload to take effect"
            ),
        }
    )


@app.post("/api/v1/coverage/blacklist/{obj_id}/remove", response_model=SampleMutationPayload)
def remove_coverage_blacklist_mutation(
    obj_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _samples_repo().remove_blacklist(obj_id)
    return util.common.convert_to_serializable(
        _mutation_payload("coverage", resource="blacklist", resource_id=obj_id, action="remove")
    )

