"""Canonical classification router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from api.app.container import util
from api.app.deps.application import get_sample
from api.interfaces.http.tags import TAG_KNOWLEDGEBASE
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.models import TierChange
from coyote3.application.operations.samples import Sample
from coyote3.contracts.samples import SampleChangePayload

router = APIRouter(tags=[TAG_KNOWLEDGEBASE])


@router.patch(
    "/api/v1/samples/{sample_id}/classifications/tier",
    response_model=SampleChangePayload,
    summary="Bulk tier classification update",
)
def set_resource_tier_bulk(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: Sample = Depends(get_sample),
):
    """Apply or remove a tier classification across multiple resources."""
    resource_type = str(payload.get("resource_type", "small_variant"))
    resource_ids = payload.get("resource_ids", payload.get("variant_ids", [])) or []
    try:
        tier = int(payload.get("tier", 3))
    except (TypeError, ValueError):
        tier = 3
    if tier not in {1, 2, 3, 4}:
        tier = 3
    service.set_tiers(
        TierChange(
            resource_type=resource_type,
            resource_ids=resource_ids,
            tier=tier,
            apply=bool(payload.get("apply", True)),
            include_automatic_text=bool(payload.get("include_automatic_text", False)),
        )
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
    user: ApiUser = Depends(require_access(permission="tier:assign")),
    service: Sample = Depends(get_sample),
):
    """Create a classification for a resource."""
    target_id = str(payload.get("id", "unknown"))
    service.classify(
        str(payload.get("resource_type", "small_variant")),
        target_id,
        payload.get("form_data", {}) or {},
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="classification", resource_id=target_id, action="classify"
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
    user: ApiUser = Depends(require_access(permission="tier:remove:own")),
    service: Sample = Depends(get_sample),
):
    """Remove a classification from a resource."""
    target_id = str(payload.get("id", "unknown"))
    service.remove_classification(
        str(payload.get("resource_type", "small_variant")),
        target_id,
        payload.get("form_data", {}) or {},
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
