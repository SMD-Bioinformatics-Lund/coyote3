"""RNA mutation routes (fusion flags and comments)."""

from __future__ import annotations

from fastapi import Depends, Query

from api.extensions import store, util
from api.infra.repositories.rna_route_mongo import MongoRNARouteRepository
from api.app import app
from api.contracts.samples import SampleMutationPayload
from api.security.access import ApiUser, _get_sample_for_api, require_access

def _rna_repo() -> MongoRNARouteRepository:
    from api.infra.repositories import rna_route_mongo

    rna_route_mongo.store = store
    return MongoRNARouteRepository()


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp", response_model=SampleMutationPayload)
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


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp", response_model=SampleMutationPayload)
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


@app.post(
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


@app.post(
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


@app.post(
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


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/fp", response_model=SampleMutationPayload)
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


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant", response_model=SampleMutationPayload)
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
