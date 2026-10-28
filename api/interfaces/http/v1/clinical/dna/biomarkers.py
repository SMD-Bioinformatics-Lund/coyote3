"""Sample-scoped HRD, MSI, and TMB HTTP resources."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.application import get_sample
from api.interfaces.http.tags import TAG_HRD, TAG_MSI, TAG_TMB
from api.security.access import ApiUser, require_access
from coyote3.application.operations.samples import Sample
from coyote3.contracts.dna import (
    BiomarkerAssessmentRequest,
    DnaBiomarkersPayload,
    DnaHrdPayload,
    DnaMsiPayload,
    DnaTmbPayload,
)

router = APIRouter()


@router.get(
    "/api/v1/samples/{sample_id}/biomarkers",
    response_model=DnaBiomarkersPayload,
    tags=[TAG_HRD, TAG_MSI, TAG_TMB],
)
def review_dna_biomarkers(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Read enabled DNA biomarker measurements and manually assigned assessments.

    Requires sample:view and sample access. Missing assessments remain unassessed;
    numeric thresholds are never used to assign a clinical value.
    """
    return util.common.convert_to_serializable(service.biomarker_review())


@router.patch(
    "/api/v1/samples/{sample_id}/biomarkers/{record_id}/assessments/{method}",
    response_model=DnaBiomarkersPayload,
    tags=[TAG_HRD, TAG_MSI, TAG_TMB],
)
def assess_dna_biomarker(
    sample_id: str,
    record_id: str,
    method: str,
    payload: BiomarkerAssessmentRequest,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Save HIGH, MODERATE, LOW or clear a manual biomarker assessment.

    Requires sample edit access and an active sample-biomarkers editing lease.
    Production samples additionally require annotation:publish. The measurement must
    belong to this sample and be enabled in its stored ASPC. A stale revision returns
    409; measured scores are preserved. Actor and assessment time are recorded by the server.
    """
    return util.common.convert_to_serializable(service.assess_biomarker(record_id, method, payload))


@router.get("/api/v1/samples/{sample_id}/hrd", response_model=DnaHrdPayload, tags=[TAG_HRD])
def list_dna_hrd(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
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
    return util.common.convert_to_serializable(service.biomarkers("HRD"))


@router.get("/api/v1/samples/{sample_id}/msi", response_model=DnaMsiPayload, tags=[TAG_MSI])
def list_dna_msi(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
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
    return util.common.convert_to_serializable(service.biomarkers("MSI"))


@router.get("/api/v1/samples/{sample_id}/tmb", response_model=DnaTmbPayload, tags=[TAG_TMB])
def list_dna_tmb(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
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
    return util.common.convert_to_serializable(service.biomarkers("TMB"))
