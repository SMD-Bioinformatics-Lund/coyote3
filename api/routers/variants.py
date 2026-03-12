"""Canonical DNA and variant router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.contracts.dna import (
    DnaBiomarkersPayload,
    DnaPlotContextPayload,
    DnaVariantContextPayload,
    DnaVariantsListPayload,
)
from api.contracts.samples import SampleMutationPayload
from api.core.dna.dna_filters import get_filter_conseq_terms
from api.core.dna.dna_reporting import hotspot_variant
from api.core.dna.dna_variants import format_pon, get_variant_nomenclature
from api.core.dna.notation import one_letter_p
from api.core.dna.query_builders import build_query
from api.core.interpretation.annotation_enrichment import add_alt_class, add_global_annotations
from api.core.interpretation.report_summary import (
    create_annotation_text_from_gene,
    create_comment_doc,
    generate_summary_text,
)
from api.deps.services import get_dna_service
from api.extensions import util
from api.http import api_error as _api_error, get_formatted_assay_config as _get_formatted_assay_config
from api.services.dna_service import DnaService
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["dna"])

@router.get("/api/v1/dna/samples/{sample_id}/variants", response_model=DnaVariantsListPayload)
def list_dna_variants(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_variants_payload(
            request=request,
            sample=sample,
            util_module=util,
            add_global_annotations_fn=add_global_annotations,
            generate_summary_text_fn=generate_summary_text,
            build_query_fn=build_query,
            get_filter_conseq_terms_fn=get_filter_conseq_terms,
            assay_config_getter=_get_formatted_assay_config,
        )
    )


@router.get("/api/v1/dna/samples/{sample_id}/plot_context", response_model=DnaPlotContextPayload)
def dna_plot_context(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.plot_context_payload(sample=sample, assay_config_getter=_get_formatted_assay_config)
    )


@router.get("/api/v1/dna/samples/{sample_id}/biomarkers", response_model=DnaBiomarkersPayload)
def list_dna_biomarkers(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.biomarkers_payload(sample=sample))


@router.get("/api/v1/dna/samples/{sample_id}/variants/{var_id}", response_model=DnaVariantContextPayload)
def show_dna_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.variant_context_payload(
            sample=sample,
            var_id=var_id,
            add_alt_class_fn=add_alt_class,
            util_module=util,
            assay_config_getter=_get_formatted_assay_config,
        )
    )


def _require_variant_for_sample(sample_id: str, var_id: str, user: ApiUser, service: DnaService) -> tuple[dict, dict]:
    sample = _get_sample_for_api(sample_id, user)
    variant = service.require_variant_for_sample(sample=sample, var_id=var_id)
    return sample, variant


@router.delete("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Remove false-positive flag from variant")
def unmark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.unmark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_false_positive")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/false-positive", response_model=SampleMutationPayload, summary="Mark variant false-positive")
def mark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.mark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_false_positive")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/interesting", response_model=SampleMutationPayload, summary="Remove interesting flag from variant")
def unmark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.unmark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_interesting")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/interesting", response_model=SampleMutationPayload, summary="Mark variant interesting")
def mark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.mark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_interesting")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/irrelevant", response_model=SampleMutationPayload, summary="Remove irrelevant flag from variant")
def unmark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.unmark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_irrelevant")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/{var_id}/flags/irrelevant", response_model=SampleMutationPayload, summary="Mark variant irrelevant")
def mark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.mark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_irrelevant")
    )


@router.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist-entries", response_model=SampleMutationPayload, summary="Create blacklist entry from variant")
def add_variant_to_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    sample, variant = _require_variant_for_sample(sample_id, var_id, user, service)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    service.repository.blacklist_handler.blacklist_variant(variant, assay_group)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant", resource_id=var_id, action="blacklist")
    )


@router.patch(
    "/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Hide variant comment",
)
def hide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.hide_var_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="hide")
    )


@router.delete(
    "/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Unhide variant comment",
)
def unhide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaService = Depends(get_dna_service),
):
    _require_variant_for_sample(sample_id, var_id, user, service)
    service.repository.variant_handler.unhide_variant_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="unhide")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/flags/false-positive", response_model=SampleMutationPayload, summary="Bulk false-positive variant update")
def set_variant_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    _get_sample_for_api(sample_id, user)
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_variant_ids, list):
        variant_ids = payload_variant_ids
    apply = service.coerce_bool(payload.get("apply") if isinstance(payload, dict) else None, default=apply)
    service.set_variant_bulk_flag(variant_ids=variant_ids, apply=apply, flag="false_positive")
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/flags/irrelevant", response_model=SampleMutationPayload, summary="Bulk irrelevant variant update")
def set_variant_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    _get_sample_for_api(sample_id, user)
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_variant_ids, list):
        variant_ids = payload_variant_ids
    apply = service.coerce_bool(payload.get("apply") if isinstance(payload, dict) else None, default=apply)
    service.set_variant_bulk_flag(variant_ids=variant_ids, apply=apply, flag="irrelevant")
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )


@router.patch("/api/v1/dna/samples/{sample_id}/variants/tier", response_model=SampleMutationPayload, summary="Bulk tier variant update")
def set_variant_tier_bulk(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    sample = _get_sample_for_api(sample_id, user)
    variant_ids = payload.get("variant_ids", []) or []
    assay_group = payload.get("assay_group")
    subpanel = payload.get("subpanel")
    apply = service.coerce_bool(payload.get("apply", True), default=True)
    tier_raw = payload.get("tier", 3)
    try:
        class_num = int(tier_raw)
    except (TypeError, ValueError):
        class_num = 3
    if class_num not in {1, 2, 3, 4}:
        class_num = 3
    if variant_ids:
        service.set_variant_tier_bulk(
            sample=sample,
            variant_ids=variant_ids,
            assay_group=assay_group,
            subpanel=subpanel,
            apply=apply,
            class_num=class_num,
            create_annotation_text_fn=create_annotation_text_from_gene,
            create_classified_variant_doc_fn=util.common.create_classified_variant_doc,
        )

    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_tier_bulk")
    )


@router.post("/api/v1/dna/samples/{sample_id}/variant-classifications", response_model=SampleMutationPayload, status_code=201, summary="Create variant classification")
def classify_variant_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assign_tier", min_role="manager", min_level=99)),
    service: DnaService = Depends(get_dna_service),
):
    _get_sample_for_api(sample_id, user)
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    service.classify_variant(
        form_data=form_data,
        get_tier_classification_fn=util.common.get_tier_classification,
        get_variant_nomenclature_fn=get_variant_nomenclature,
    )
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="classification", resource_id=target_id, action="classify")
    )


@router.delete("/api/v1/dna/samples/{sample_id}/variant-classifications", response_model=SampleMutationPayload, summary="Delete variant classification")
def remove_classified_variant_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="remove_tier", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    _get_sample_for_api(sample_id, user)
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    service.remove_classified_variant(form_data=form_data, get_variant_nomenclature_fn=get_variant_nomenclature)
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource="classification", resource_id=target_id, action="remove_classified")
    )


@router.post("/api/v1/dna/samples/{sample_id}/variant-comments", response_model=SampleMutationPayload, status_code=201, summary="Create DNA variant/fusion/translocation/CNV comment")
def add_variant_comment_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="add_variant_comment", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    _get_sample_for_api(sample_id, user)
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    resource = service.add_variant_comment(
        form_data=form_data,
        target_id=target_id,
        get_variant_nomenclature_fn=get_variant_nomenclature,
        create_comment_doc_fn=create_comment_doc,
    )
    return util.common.convert_to_serializable(
        service.mutation_payload(sample_id, resource=resource, resource_id=target_id, action="add_comment")
    )
