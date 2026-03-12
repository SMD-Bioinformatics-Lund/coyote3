"""Canonical DNA structural router module."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import (
    DnaCnvContextPayload,
    DnaCnvListPayload,
    DnaTranslocationContextPayload,
    DnaTranslocationsPayload,
)
from api.contracts.samples import SampleMutationPayload
from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.core.dna.query_builders import build_cnv_query
from api.extensions import store, util
from api.http import api_error as _api_error, get_formatted_assay_config as _get_formatted_assay_config
from api.repositories.dna_repository import DnaRouteRepository as MongoDNARouteRepository
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["dna-structural"])

if not hasattr(util, "common"):
    util.init_util()


def _dna_repo() -> MongoDNARouteRepository:
    from api.infra.repositories import dna_route_mongo

    dna_route_mongo.store = store
    return MongoDNARouteRepository()


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _load_cnvs_for_sample(sample: dict, sample_filters: dict, filter_genes: list[str]) -> list[dict]:
    cnv_query = build_cnv_query(str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes})
    cnvs = list(_dna_repo().cnv_handler.get_sample_cnvs(cnv_query))
    filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
    if filter_cnveffects:
        cnvs = cnvtype_variant(cnvs, filter_cnveffects)
    return cnv_organizegenes(cnvs)


@router.get("/api/v1/dna/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))
    assay_panel_doc = _dna_repo().asp_handler.get_asp(asp_name=sample.get("assay"))
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict = _dna_repo().isgl_handler.get_isgl_by_ids(checked_genelists)
    _genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )
    cnvs = _load_cnvs_for_sample(sample, sample_filters, filter_genes)

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {"request_path": request.url.path, "count": len(cnvs)},
        "filters": sample_filters,
        "cnvs": cnvs,
    }
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(sample_id: str, cnv_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    cnv = _dna_repo().cnv_handler.get_cnv(cnv_id)
    if not cnv:
        raise _api_error(404, "CNV not found")
    cnv_sample_id = cnv.get("SAMPLE_ID") or cnv.get("sample_id")
    if cnv_sample_id and str(cnv_sample_id) != str(sample.get("_id")):
        raise _api_error(404, "CNV not found for sample")
    if not cnv_sample_id:
        sample_cnvs = list(_dna_repo().cnv_handler.get_sample_cnvs({"SAMPLE_ID": str(sample.get("_id"))}))
        sample_cnv_ids = {str(doc.get("_id")) for doc in sample_cnvs}
        if str(cnv.get("_id")) not in sample_cnv_ids:
            raise _api_error(404, "CNV not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
    sample_ids = util.common.get_case_and_control_sample_ids(sample)

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
        },
        "cnv": cnv,
        "annotations": _dna_repo().cnv_handler.get_cnv_annotations(cnv),
        "sample_ids": sample_ids,
        "bam_id": _dna_repo().bam_service_handler.get_bams(sample_ids),
        "has_hidden_comments": _dna_repo().cnv_handler.hidden_cnv_comments(cnv_id),
        "hidden_comments": _dna_repo().cnv_handler.hidden_cnv_comments(cnv_id),
        "assay_group": assay_group,
    }
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/dna/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))
):
    sample = _get_sample_for_api(sample_id, user)
    translocs = list(_dna_repo().transloc_handler.get_sample_translocations(sample_id=str(sample["_id"])))
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {"request_path": request.url.path, "count": len(translocs)},
        "translocations": translocs,
    }
    return util.common.convert_to_serializable(payload)


@router.get(
    "/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str, transloc_id: str, user: ApiUser = Depends(require_access(min_level=1))
):
    sample = _get_sample_for_api(sample_id, user)
    transloc = _dna_repo().transloc_handler.get_transloc(transloc_id)
    if not transloc:
        raise _api_error(404, "Translocation not found")
    transloc_sample_id = transloc.get("SAMPLE_ID") or transloc.get("sample_id")
    if transloc_sample_id and str(transloc_sample_id) != str(sample.get("_id")):
        raise _api_error(404, "Translocation not found for sample")
    if not transloc_sample_id:
        sample_translocs = list(_dna_repo().transloc_handler.get_sample_translocations(sample_id=str(sample.get("_id"))))
        sample_transloc_ids = {str(doc.get("_id")) for doc in sample_translocs}
        if str(transloc.get("_id")) not in sample_transloc_ids:
            raise _api_error(404, "Translocation not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
    sample_ids = util.common.get_case_and_control_sample_ids(sample)

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
        },
        "translocation": transloc,
        "annotations": _dna_repo().transloc_handler.get_transloc_annotations(transloc),
        "sample_ids": sample_ids,
        "bam_id": _dna_repo().bam_service_handler.get_bams(sample_ids),
        "vep_conseq_translations": _dna_repo().vep_meta_handler.get_conseq_translations(sample.get("vep", 103)),
        "has_hidden_comments": _dna_repo().transloc_handler.hidden_transloc_comments(transloc_id),
        "hidden_comments": _dna_repo().transloc_handler.hidden_transloc_comments(transloc_id),
        "assay_group": assay_group,
    }
    return util.common.convert_to_serializable(payload)


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting", response_model=SampleMutationPayload)
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.unmark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_interesting")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting", response_model=SampleMutationPayload)
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.mark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_interesting")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv", response_model=SampleMutationPayload)
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.mark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_false_positive")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv", response_model=SampleMutationPayload)
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.unmark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_false_positive")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv", response_model=SampleMutationPayload)
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.noteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_noteworthy")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv", response_model=SampleMutationPayload)
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.unnoteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_noteworthy")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide", response_model=SampleMutationPayload)
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_variant_comment", min_role="manager", min_level=99)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="hide")
    )


@router.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide", response_model=SampleMutationPayload)
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="unhide")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc", response_model=SampleMutationPayload)
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.mark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="mark_interesting")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc", response_model=SampleMutationPayload)
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.unmark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="unmark_interesting")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc", response_model=SampleMutationPayload)
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.mark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="mark_false_positive")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc", response_model=SampleMutationPayload)
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.unmark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation", resource_id=transloc_id, action="unmark_false_positive")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide", response_model=SampleMutationPayload)
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="hide_variant_comment", min_role="manager", min_level=99)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="hide")
    )


@router.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide", response_model=SampleMutationPayload)
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)),
):
    _get_sample_for_api(sample_id, user)
    _dna_repo().transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="unhide")
    )
