"""Canonical RNA router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.contracts.rna import RnaFusionContextPayload, RnaFusionListPayload
from api.contracts.samples import SampleMutationPayload
from api.core.interpretation.annotation_enrichment import add_global_annotations
from api.core.interpretation.report_summary import generate_summary_text
from api.core.workflows.rna_workflow import RNAWorkflowService
from api.extensions import store, util
from api.http import api_error as _api_error, get_formatted_assay_config as _get_formatted_assay_config
from api.repositories.rna_repository import RnaRouteRepository as MongoRNARouteRepository
from api.repositories.rna_repository import RnaWorkflowRepository as MongoRNAWorkflowRepository
from api.runtime import app as runtime_app
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["rna"])


class _HandlerStub:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


_RNA_TESTABLE_STORE_HANDLERS = (
    "schema_handler",
    "asp_handler",
    "isgl_handler",
    "sample_handler",
    "fusion_handler",
)

for _handler_name in _RNA_TESTABLE_STORE_HANDLERS:
    if not hasattr(store, _handler_name):
        setattr(store, _handler_name, _HandlerStub())

if not hasattr(util, "common"):
    util.init_util()


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _rna_repo() -> MongoRNARouteRepository:
    from api.infra.repositories import rna_route_mongo

    rna_route_mongo.store = store
    return MongoRNARouteRepository()


def _rna_workflow_service() -> type[RNAWorkflowService]:
    if not RNAWorkflowService.has_repository():
        RNAWorkflowService.set_repository(MongoRNAWorkflowRepository())
    return RNAWorkflowService


@router.get("/api/v1/rna/samples/{sample_id}/fusions", response_model=RnaFusionListPayload)
def list_rna_fusions(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    _rna_workflow_service()
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, assay_config, sample_id, runtime_app.logger
    )
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    assay_config_schema = _rna_repo().schema_handler.get_schema(assay_config.get("schema_name"))
    assay_panel_doc = _rna_repo().asp_handler.get_asp(asp_name=sample.get("assay"))
    fusionlist_options = _rna_repo().isgl_handler.get_isgl_by_asp(
        sample.get("assay"), is_active=True, list_type="fusionlist"
    )
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    has_hidden_comments = _rna_repo().sample_handler.hidden_sample_comments(sample.get("_id"))
    filter_context = RNAWorkflowService.compute_filter_context(
        sample=sample, sample_filters=sample_filters, assay_panel_doc=assay_panel_doc
    )
    query = RNAWorkflowService.build_fusion_list_query(
        assay_group=assay_group,
        sample_id=str(sample["_id"]),
        sample_filters=sample_filters,
        filter_context=filter_context,
    )
    fusions = list(_rna_repo().fusion_handler.get_sample_fusions(query))
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


@router.get("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}", response_model=RnaFusionContextPayload)
def show_rna_fusion(sample_id: str, fusion_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    _rna_workflow_service()
    sample = _get_sample_for_api(sample_id, user)
    fusion = _rna_repo().fusion_handler.get_fusion(fusion_id)
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


@router.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp", response_model=SampleMutationPayload)
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    _rna_repo().fusion_handler.mark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="mark_false_positive")
    )


@router.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp", response_model=SampleMutationPayload)
def unmark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    _rna_repo().fusion_handler.unmark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="unmark_false_positive")
    )


@router.post(
    "/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/pick/{callidx}/{num_calls}",
    response_model=SampleMutationPayload,
)
def pick_fusion_call(
    sample_id: str,
    fusion_id: str,
    callidx: str,
    num_calls: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    _rna_repo().fusion_handler.pick_fusion(fusion_id, callidx, num_calls)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="pick_fusion_call")
    )


@router.post(
    "/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hide",
    response_model=SampleMutationPayload,
)
def hide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    _rna_repo().fusion_handler.hide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="hide")
    )


@router.post(
    "/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/unhide",
    response_model=SampleMutationPayload,
)
def unhide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    _rna_repo().fusion_handler.unhide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="unhide")
    )


@router.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/fp", response_model=SampleMutationPayload)
def set_fusion_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        _rna_repo().fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@router.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant", response_model=SampleMutationPayload)
def set_fusion_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        _rna_repo().fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )
