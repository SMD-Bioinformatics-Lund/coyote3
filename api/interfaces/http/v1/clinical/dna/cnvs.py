"""Canonical CNV router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.app.container import util
from api.app.deps.application import get_cnvs
from api.interfaces.http.tags import TAG_DNA_CNV
from api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.clinical import Findings
from coyote3.contracts.dna import (
    DnaCnvContextPayload,
    DnaCnvListPayload,
    DnaCsvExportContextPayload,
)
from coyote3.contracts.samples import SampleChangePayload

router = APIRouter(tags=[TAG_DNA_CNV])


@router.get("/api/v1/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_cnvs),
):
    """Return CNVs for a sample."""
    return util.common.convert_to_serializable(service.view(analysis_query_from_request(request)))


@router.get(
    "/api/v1/samples/{sample_id}/cnvs/exports/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered CNV CSV export context",
)
def export_cnv_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:download")),
    service: Findings = Depends(get_cnvs),
):
    """Build CNV export payload from the sample's active CNV filters."""
    return util.common.convert_to_serializable(
        service.export_csv(analysis_query_from_request(request)).model_dump()
    )


@router.get("/api/v1/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_cnvs),
):
    """Return CNV detail payload."""
    return util.common.convert_to_serializable(service.context(cnv_id))


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from CNV",
)
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Remove the interesting flag from a CNV."""
    operation = service.set_flag(cnv_id, flag="interesting", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="unmark_interesting",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark CNV interesting",
)
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Mark a CNV as interesting."""
    operation = service.set_flag(cnv_id, flag="interesting", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="mark_interesting",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark CNV false-positive",
)
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Mark a CNV as false positive."""
    operation = service.set_flag(cnv_id, flag="false_positive", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="mark_false_positive",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from CNV",
)
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Remove the false-positive flag from a CNV."""
    operation = service.set_flag(cnv_id, flag="false_positive", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="unmark_false_positive",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleChangePayload,
    summary="Mark CNV noteworthy",
)
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Mark a CNV as noteworthy."""
    operation = service.set_flag(cnv_id, flag="noteworthy", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="mark_noteworthy",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy",
    response_model=SampleChangePayload,
    summary="Remove noteworthy flag from CNV",
)
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: Findings = Depends(get_cnvs),
):
    """Remove the noteworthy flag from a CNV."""
    operation = service.set_flag(cnv_id, flag="noteworthy", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="cnv",
            resource_id=cnv_id,
            action="unmark_noteworthy",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide CNV comment",
)
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="variant.comment:hide")),
    service: Findings = Depends(get_cnvs),
):
    """Hide a CNV comment."""
    service.set_comment_hidden(cnv_id, comment_id, hidden=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="cnv_comment", resource_id=comment_id, action="hide"
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide CNV comment",
)
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="variant.comment:unhide")),
    service: Findings = Depends(get_cnvs),
):
    """Unhide a CNV comment."""
    service.set_comment_hidden(cnv_id, comment_id, hidden=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="cnv_comment", resource_id=comment_id, action="unhide"
        )
    )
