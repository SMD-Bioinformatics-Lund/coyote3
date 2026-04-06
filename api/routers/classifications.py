"""Canonical classification router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from api.contracts.samples import SampleChangePayload
from api.core.dna.dna_variants import get_variant_nomenclature
from api.deps.services import get_classification_service
from api.extensions import util
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.classification.tiering import ResourceClassificationService
from api.services.common.change_payload import change_payload
from api.services.interpretation.report_summary import create_annotation_text_from_gene

router = APIRouter(tags=["classifications"])


@router.patch(
    "/api/v1/samples/{sample_id}/classifications/tier",
    response_model=SampleChangePayload,
    summary="Bulk tier classification update",
)
def set_resource_tier_bulk(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: ResourceClassificationService = Depends(get_classification_service),
):
    """Apply or remove a tier classification across multiple resources."""
    sample = _get_sample_for_api(sample_id, user)
    resource_type = str(payload.get("resource_type", "small_variant"))
    resource_ids = payload.get("resource_ids", payload.get("variant_ids", [])) or []
    assay_group = payload.get("assay_group")
    subpanel = payload.get("subpanel")
    apply = payload.get("apply", True)
    tier_raw = payload.get("tier", 3)
    try:
        class_num = int(tier_raw)
    except (TypeError, ValueError):
        class_num = 3
    if class_num not in {1, 2, 3, 4}:
        class_num = 3
    if resource_ids:
        service.set_tier_bulk(
            sample=sample,
            resource_type=resource_type,
            resource_ids=resource_ids,
            assay_group=assay_group,
            subpanel=subpanel,
            apply=bool(apply),
            class_num=class_num,
            create_annotation_text_fn=create_annotation_text_from_gene,
            create_classified_variant_doc_fn=util.common.create_classified_variant_doc,
        )

    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="classifications",
            resource_id="bulk",
            action="set_tier_bulk",
        )
    )


@router.post(
    "/api/v1/samples/{sample_id}/classifications",
    response_model=SampleChangePayload,
    status_code=201,
    summary="Create classification",
)
def classify_resource_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="assign_tier", min_role="manager", min_level=99)
    ),
    service: ResourceClassificationService = Depends(get_classification_service),
):
    """Create a classification for a resource."""
    _get_sample_for_api(sample_id, user)
    resource_type = str(payload.get("resource_type", "small_variant"))
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    service.classify_resource(
        resource_type=resource_type,
        form_data=form_data,
        get_tier_classification_fn=util.common.get_tier_classification,
        get_variant_nomenclature_fn=get_variant_nomenclature,
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="classification",
            resource_id=target_id,
            action="classify",
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/classifications",
    response_model=SampleChangePayload,
    summary="Delete classification",
)
def remove_classified_resource_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="remove_tier", min_role="admin")),
    service: ResourceClassificationService = Depends(get_classification_service),
):
    """Remove a classification from a resource."""
    _get_sample_for_api(sample_id, user)
    resource_type = str(payload.get("resource_type", "small_variant"))
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    service.remove_resource(
        resource_type=resource_type,
        form_data=form_data,
        get_variant_nomenclature_fn=get_variant_nomenclature,
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="classification",
            resource_id=target_id,
            action="remove_classified",
        )
    )


__all__ = [
    "classify_resource_change",
    "remove_classified_resource_change",
    "router",
    "set_resource_tier_bulk",
]
