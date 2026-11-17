# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Typed read-only metadata queries for authenticated integrations."""

from coyote.application.operations.resource_reads import ResourceReads
from coyote.domain.common.errors import api_error
from coyote_contracts.retrieval import ReadResource, ResourceReadPage, ResourceReadQuery
from fastapi import APIRouter, Depends, Request

from coyote_api.app.deps.application import get_resource_reads
from coyote_api.interfaces.http.tags import TAG_RESOURCE_READS
from coyote_api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_RESOURCE_READS])


@router.post("/api/v1/resources/read/{resource}/query", response_model=ResourceReadPage)
def query_resources(
    resource: ReadResource,
    query: ResourceReadQuery,
    request: Request,
    user: ApiUser = Depends(require_access()),
    service: ResourceReads = Depends(get_resource_reads),
) -> ResourceReadPage:
    """Read allowlisted metadata, IDs, counts, existence or distinct field values.

    Requires sample:view, assay.panel:view, assay.config:view, or
    gene_list.insilico:view according to resource. ASP, ASPC and ISGL queries
    also require their :list permission. Related sample records require
    their own view permission. Exact clinical scope applies to every operation.
    All query options belong in the JSON body; unknown names are rejected.
    """
    if request.query_params:
        raise api_error(422, "Resource read options belong in the JSON body")
    return service.query(resource, query)
