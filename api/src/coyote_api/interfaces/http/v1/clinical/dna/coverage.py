# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Canonical coverage router module."""

from __future__ import annotations

from coyote.application.operations.coverage import Coverage
from coyote.application.operations.samples import Sample
from coyote.contracts.coverage import CoverageBlacklistedPayload, CoverageSamplePayload
from fastapi import APIRouter, Depends, Query

from coyote_api.app.deps.application import get_coverage, get_sample
from coyote_api.app.deps.modules import RequireModules
from coyote_api.app.utilities.serialization import convert_to_serializable
from coyote_api.interfaces.http.tags import TAG_COVERAGE
from coyote_api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_COVERAGE], dependencies=[Depends(RequireModules("dna_analysis"))])


@router.get("/api/v1/samples/{sample_id}/coverage", response_model=CoverageSamplePayload)
def coverage_sample_read(
    sample_id: str,
    cov_cutoff: int = Query(default=500, ge=1),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
    gene_list_id: str | None = None,
):
    """Return coverage data for a sample.

    \u000c

    Args:
        sample_id: Sample identifier to inspect.
        cov_cutoff: Coverage threshold for low-coverage detection.
        user: Authenticated user requesting coverage data.
        service: Coverage workflow service.
        gene_list_id: Optional captured list narrowing the assay coverage scope.

    Returns:
        dict: Coverage payload for the requested sample.
    """
    return convert_to_serializable(service.coverage(cutoff=cov_cutoff, gene_list_id=gene_list_id))


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
    return convert_to_serializable(service.blacklisted(group))
