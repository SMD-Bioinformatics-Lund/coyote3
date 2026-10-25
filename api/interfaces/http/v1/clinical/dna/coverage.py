"""Canonical coverage router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.app.container import util
from api.app.deps.application import get_coverage, get_sample
from api.interfaces.http.tags import TAG_COVERAGE
from api.security.access import ApiUser, require_access
from coyote3.application.operations.coverage import Coverage
from coyote3.application.operations.samples import Sample
from coyote3.contracts.coverage import CoverageBlacklistedPayload, CoverageSamplePayload

router = APIRouter(tags=[TAG_COVERAGE])


@router.get("/api/v1/samples/{sample_id}/coverage", response_model=CoverageSamplePayload)
def coverage_sample_read(
    sample_id: str,
    cov_cutoff: int = Query(default=500, ge=1),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Return coverage data for a sample.

    \u000c

    Args:
        sample_id: Sample identifier to inspect.
        cov_cutoff: Coverage threshold for low-coverage detection.
        user: Authenticated user requesting coverage data.
        service: Coverage workflow service.

    Returns:
        dict: Coverage payload for the requested sample.
    """
    return util.common.convert_to_serializable(service.coverage(cutoff=cov_cutoff))


@router.get("/api/v1/coverage/blacklisted/{group}", response_model=CoverageBlacklistedPayload)
def coverage_blacklisted_read(
    group: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Coverage = Depends(get_coverage),
):
    """Return blacklisted coverage regions for an assay group.

    \u000c

    Args:
        group: Assay group to inspect.
        user: Authenticated user requesting blacklist data.
        service: Coverage workflow service.

    Returns:
        dict: Blacklisted-region payload for the assay group.
    """
    return util.common.convert_to_serializable(service.blacklisted(group))
