"""Canonical biomarker router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.services import get_biomarker_service
from api.application.biomarker.biomarker_lookup import BiomarkerService
from api.contracts.dna import DnaBiomarkersPayload
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["biomarkers"])


@router.get("/api/v1/samples/{sample_id}/biomarkers", response_model=DnaBiomarkersPayload)
def list_dna_biomarkers(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: BiomarkerService = Depends(get_biomarker_service),
):
    """Return biomarker data for a sample.

    Args:
        sample_id: Sample identifier to inspect.
        user: Authenticated user requesting biomarker data.
        service: Biomarker workflow service.

    Returns:
        dict: Biomarker payload for the requested sample.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.list_payload(sample=sample))


__all__ = ["list_dna_biomarkers", "router"]
