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
    """Coverage sample read.

    Args:
        sample_id (str): Value for ``sample_id``.
        cov_cutoff (int): Value for ``cov_cutoff``.
        user (ApiUser): Value for ``user``.
        service (CoverageService): Value for ``service``.

    Returns:
        The function result.
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
    """Coverage blacklisted read.

    Args:
        group (str): Value for ``group``.
        user (ApiUser): Value for ``user``.
        service (CoverageService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(service.blacklisted_payload(group=group, user=user))
