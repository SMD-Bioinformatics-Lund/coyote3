# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Protected server reference metadata and Prometheus endpoints."""

from coyote.application.operations.internal_references import InternalReferences
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from coyote_api.app.deps.application import get_internal_references
from coyote_api.app.utilities.serialization import convert_to_serializable
from coyote_api.contracts.internal import IsglMetaPayload, RoleLevelsPayload
from coyote_api.infra.observability.prometheus_metrics import render_prometheus_metrics
from coyote_api.interfaces.http.tags import TAG_INTERNAL
from coyote_api.security.access import _require_internal_token

router = APIRouter(tags=[TAG_INTERNAL])


@router.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(
    request: Request, service: InternalReferences = Depends(get_internal_references)
):
    """Return role-level mappings for trusted internal callers."""
    return convert_to_serializable(service.role_levels())


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    service: InternalReferences = Depends(get_internal_references),
):
    """Return genelist metadata for trusted internal callers."""
    return convert_to_serializable(service.gene_list_metadata(isgl_id))


@router.get("/api/v1/internal/metrics", response_class=PlainTextResponse)
def get_prometheus_metrics_internal(request: Request):
    """Expose Prometheus metrics in text format for internal scraping."""
    _require_internal_token(request)
    return PlainTextResponse(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
