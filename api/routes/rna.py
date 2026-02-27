"""RNA API routes."""

from fastapi import Depends, Query, Request

from api.extensions import store, util
from api.services.interpretation.annotation_enrichment import add_global_annotations
from api.services.interpretation.report_summary import generate_summary_text
from api.services.workflow.rna_workflow import RNAWorkflowService
from api.app import (
    ApiUser,
    _api_error,
    _get_formatted_assay_config,
    _get_sample_for_api,
    app,
    flask_app,
    require_access,
)


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@app.get("/api/v1/rna/samples/{sample_id}/fusions")
def list_rna_fusions(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, assay_config, sample_id, flask_app.logger
    )
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    assay_config_schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample.get("assay"))
    fusionlist_options = store.isgl_handler.get_isgl_by_asp(
        sample.get("assay"), is_active=True, list_type="fusionlist"
    )
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))
    filter_context = RNAWorkflowService.compute_filter_context(
        sample=sample, sample_filters=sample_filters, assay_panel_doc=assay_panel_doc
    )
    query = RNAWorkflowService.build_fusion_list_query(
        assay_group=assay_group,
        sample_id=str(sample["_id"]),
        sample_filters=sample_filters,
        filter_context=filter_context,
    )
    fusions = list(store.fusion_handler.get_sample_fusions(query))
    fusions, tiered_fusions = add_global_annotations(fusions, assay_group, subpanel)
    sample = RNAWorkflowService.attach_rna_analysis_sections(sample)
    summary_sections_data = {"fusions": tiered_fusions}
    ai_text = generate_summary_text(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_context["filter_genes"],
        filter_context["checked_fusionlists"],
    )

    payload = {
        "sample": sample,
        "meta": {"request_path": request.url.path, "count": len(fusions), "tiered": tiered_fusions},
        "assay_group": assay_group,
        "subpanel": subpanel,
        "analysis_sections": assay_config.get("analysis_types", []),
        "assay_config": assay_config,
        "assay_config_schema": assay_config_schema,
        "assay_panel_doc": assay_panel_doc,
        "sample_ids": sample_ids,
        "hidden_comments": has_hidden_comments,
        "fusionlist_options": fusionlist_options,
        "checked_fusionlists": filter_context.get("checked_fusionlists", []),
        "checked_fusionlists_dict": filter_context.get("genes_covered_in_panel", {}),
        "filters": sample_filters,
        "filter_context": filter_context,
        "fusions": fusions,
        "ai_text": ai_text,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}")
def show_rna_fusion(sample_id: str, fusion_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    fusion = store.fusion_handler.get_fusion(fusion_id)
    if not fusion:
        raise _api_error(404, "Fusion not found")
    if str(fusion.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Fusion not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    show_context = RNAWorkflowService.build_show_fusion_context(fusion, assay_group, subpanel)

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
            "subpanel": subpanel,
        },
        "fusion": show_context["fusion"],
        "in_other": show_context["in_other"],
        "annotations": show_context["annotations"],
        "latest_classification": show_context["latest_classification"],
        "annotations_interesting": show_context["annotations_interesting"],
        "other_classifications": show_context["other_classifications"],
        "has_hidden_comments": show_context["hidden_comments"],
        "hidden_comments": show_context["hidden_comments"],
        "assay_group": assay_group,
        "subpanel": subpanel,
        "assay_group_mappings": show_context["assay_group_mappings"],
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp")
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.mark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="mark_false_positive")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp")
def unmark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.unmark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="unmark_false_positive")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/pick/{callidx}/{num_calls}")
def pick_fusion_call(
    sample_id: str,
    fusion_id: str,
    callidx: str,
    num_calls: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.pick_fusion(fusion_id, callidx, num_calls)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="pick_fusion_call")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hide")
def hide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.hide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/unhide")
def unhide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.unhide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="unhide")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/fp")
def set_fusion_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        store.fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant")
def set_fusion_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        store.fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )
