"""Canonical coverage router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.contracts.coverage import CoverageBlacklistedPayload, CoverageSamplePayload
from api.deps.services import get_coverage_service
from api.extensions import util
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.sample.coverage import CoverageService

router = APIRouter(tags=["coverage"])


@router.get("/api/v1/coverage/samples/{sample_id}", response_model=CoverageSamplePayload)
def coverage_sample_read(
    sample_id: str,
    cov_cutoff: int = Query(default=500, ge=1),
    user: ApiUser = Depends(require_access(min_level=1)),
    service: CoverageService = Depends(get_coverage_service),
):
    """Return coverage data for a sample.

    Args:
        sample_id: Sample identifier to inspect.
        cov_cutoff: Coverage threshold for low-coverage detection.
        user: Authenticated user requesting coverage data.
        service: Coverage workflow service.

    Returns:
        dict: Coverage payload for the requested sample.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.sample_payload(
            sample=sample,
            cov_cutoff=cov_cutoff,
            effective_genes_resolver=util.common.get_sample_effective_genes,
        )
    )


@router.get("/api/v1/coverage/blacklisted/{group}", response_model=CoverageBlacklistedPayload)
def coverage_blacklisted_read(
    group: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: CoverageService = Depends(get_coverage_service),
):
    """Return blacklisted coverage regions for an assay group.

    Args:
        group: Assay group to inspect.
        user: Authenticated user requesting blacklist data.
        service: Coverage workflow service.

    Returns:
        dict: Blacklisted-region payload for the assay group.
    """
    return util.common.convert_to_serializable(service.blacklisted_payload(group=group, user=user))
