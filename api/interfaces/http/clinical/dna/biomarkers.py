"""Sample-scoped HRD, MSI, and TMB HTTP resources."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.services import get_biomarker_service
from api.application.biomarker.biomarker_lookup import BiomarkerService
from api.contracts.dna import DnaHrdPayload, DnaMsiPayload, DnaTmbPayload
from api.interfaces.http.tags import TAG_HRD, TAG_MSI, TAG_TMB
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter()


@router.get("/api/v1/samples/{sample_id}/hrd", response_model=DnaHrdPayload, tags=[TAG_HRD])
def list_dna_hrd(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: BiomarkerService = Depends(get_biomarker_service),
):
    r"""Return HRD measurements enabled in the sample's stored ASPC.

    Sample access and the DNA analysis module are required.

    \f
    Args:
        sample_id: Accessible sample name or identifier.
        user: Authenticated caller with sample access.
        service: Measurement lookup service.

    Returns:
        Selected HRD records, their count, and sample context.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_payload(sample=sample, analysis_type="HRD")
    )


@router.get("/api/v1/samples/{sample_id}/msi", response_model=DnaMsiPayload, tags=[TAG_MSI])
def list_dna_msi(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: BiomarkerService = Depends(get_biomarker_service),
):
    r"""Return MSI measurements enabled in the sample's stored ASPC.

    Sample access and the DNA analysis module are required.

    \f
    Args:
        sample_id: Accessible sample name or identifier.
        user: Authenticated caller with sample access.
        service: Measurement lookup service.

    Returns:
        Selected MSI records, their count, and sample context.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_payload(sample=sample, analysis_type="MSI")
    )


@router.get("/api/v1/samples/{sample_id}/tmb", response_model=DnaTmbPayload, tags=[TAG_TMB])
def list_dna_tmb(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: BiomarkerService = Depends(get_biomarker_service),
):
    r"""Return TMB measurements enabled in the sample's stored ASPC.

    Sample access and the DNA analysis module are required.

    \f
    Args:
        sample_id: Accessible sample name or identifier.
        user: Authenticated caller with sample access.
        service: Measurement lookup service.

    Returns:
        Selected TMB records, their count, and sample context.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_payload(sample=sample, analysis_type="TMB")
    )
