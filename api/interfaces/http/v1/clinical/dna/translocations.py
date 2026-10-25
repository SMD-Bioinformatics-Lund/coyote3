"""Canonical translocation router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.app.container import util
from api.app.deps.application import get_translocations
from api.interfaces.http.tags import TAG_STRUCTURAL_VARIANTS
from api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.clinical import Findings
from coyote3.contracts.dna import (
    DnaCsvExportContextPayload,
    DnaStructuralTranscriptSelectionRequest,
    DnaTranslocationContextPayload,
    DnaTranslocationsPayload,
)
from coyote3.contracts.samples import SampleChangePayload

router = APIRouter(tags=[TAG_STRUCTURAL_VARIANTS])


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/selected-transcript",
    response_model=SampleChangePayload,
)
def select_translocation_transcript(
    sample_id: str,
    transloc_id: str,
    payload: DnaStructuralTranscriptSelectionRequest,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Select an embedded SnpEff combination for an accessible sample.

    Requires translocation:manage. Keeps all annotations on the finding; the
    selected row becomes its display and reporting anchor.
    """
    operation = service.select_translocation_transcript(transloc_id, payload.annotation_key)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="select_transcript",
            operation=operation,
        )
    )


@router.get("/api/v1/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_translocations),
):
    """Return translocations for a sample."""
    return util.common.convert_to_serializable(service.view(analysis_query_from_request(request)))


@router.get(
    "/api/v1/samples/{sample_id}/translocations/exports/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered translocation CSV export context",
)
def export_transloc_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:download")),
    service: Findings = Depends(get_translocations),
):
    """Build translocation export payload from the sample's active filters."""
    return util.common.convert_to_serializable(
        service.export_csv(analysis_query_from_request(request)).model_dump()
    )


@router.get(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Findings = Depends(get_translocations),
):
    """Return translocation detail payload."""
    return util.common.convert_to_serializable(service.context(transloc_id))


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark translocation interesting",
)
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Mark a translocation as interesting."""
    operation = service.set_flag(transloc_id, flag="interesting", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_interesting",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from translocation",
)
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Remove the interesting flag from a translocation."""
    operation = service.set_flag(transloc_id, flag="interesting", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_interesting",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark translocation false-positive",
)
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Mark a translocation as false positive."""
    operation = service.set_flag(transloc_id, flag="false_positive", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_false_positive",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from translocation",
)
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Remove the false-positive flag from a translocation."""
    operation = service.set_flag(transloc_id, flag="false_positive", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_false_positive",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Mark translocation irrelevant",
)
def mark_irrelevant_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Mark a translocation irrelevant for the current review."""
    operation = service.set_flag(transloc_id, flag="irrelevant", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_irrelevant",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Restore irrelevant translocation",
)
def unmark_irrelevant_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Restore an irrelevant translocation to the active review set."""
    operation = service.set_flag(transloc_id, flag="irrelevant", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_irrelevant",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/blacklisted",
    response_model=SampleChangePayload,
    summary="Blacklist translocation for sample",
)
def mark_blacklisted_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Apply the sample-specific structural blacklist state."""
    operation = service.set_flag(transloc_id, flag="blacklisted", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_blacklisted",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/blacklisted",
    response_model=SampleChangePayload,
    summary="Remove sample translocation blacklist",
)
def unmark_blacklisted_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: Findings = Depends(get_translocations),
):
    """Remove the sample-specific structural blacklist state."""
    operation = service.set_flag(transloc_id, flag="blacklisted", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_blacklisted",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide translocation comment",
)
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="variant.comment:hide")),
    service: Findings = Depends(get_translocations),
):
    """Hide a translocation comment."""
    service.set_comment_hidden(transloc_id, comment_id, hidden=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation_comment",
            resource_id=comment_id,
            action="hide",
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide translocation comment",
)
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(permission="variant.comment:unhide")),
    service: Findings = Depends(get_translocations),
):
    """Unhide a translocation comment."""
    service.set_comment_hidden(transloc_id, comment_id, hidden=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="translocation_comment",
            resource_id=comment_id,
            action="unhide",
        )
    )
