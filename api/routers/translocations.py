"""Canonical translocation router module."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Request

from api.contracts.dna import DnaTranslocationContextPayload, DnaTranslocationsPayload
from api.contracts.samples import SampleMutationPayload
from api.deps.services import get_translocation_service
from api.extensions import util
from api.routers.mutation_helpers import run_serialized_mutation
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.dna.translocations import TranslocationService

router = APIRouter(tags=["translocations"])

if not hasattr(util, "common"):
    util.init_util()


def _translocation_mutation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser,
    service: TranslocationService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a translocation mutation and return the canonical payload."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action=action,
        ),
        util_module=util,
    )


def _translocation_comment_mutation(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser,
    service: TranslocationService,
    *,
    action: str,
    mutate: Callable[[], None],
):
    """Execute a translocation comment visibility mutation."""
    return run_serialized_mutation(
        sample_id=sample_id,
        user=user,
        validate=lambda: _get_sample_for_api(sample_id, user),
        mutate=mutate,
        payload=lambda: service.mutation_payload(
            sample_id,
            resource="translocation_comment",
            resource_id=comment_id,
            action=action,
        ),
        util_module=util,
    )


@router.get("/api/v1/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Return translocations for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_translocations_payload(request=request, sample=sample)
    )


@router.get(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Return translocation detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_translocation_payload(sample=sample, transloc_id=transloc_id, util_module=util)
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleMutationPayload,
    summary="Mark translocation interesting",
)
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="manage_translocs", min_role="user", min_level=9)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Mark a translocation as interesting."""
    return _translocation_mutation(
        sample_id,
        transloc_id,
        user,
        service,
        action="mark_interesting",
        mutate=lambda: service.repository.transloc_handler.mark_interesting_transloc(transloc_id),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleMutationPayload,
    summary="Remove interesting flag from translocation",
)
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="manage_translocs", min_role="user", min_level=9)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Remove the interesting flag from a translocation."""
    return _translocation_mutation(
        sample_id,
        transloc_id,
        user,
        service,
        action="unmark_interesting",
        mutate=lambda: service.repository.transloc_handler.unmark_interesting_transloc(transloc_id),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleMutationPayload,
    summary="Mark translocation false-positive",
)
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="manage_translocs", min_role="user", min_level=9)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Mark a translocation as false positive."""
    return _translocation_mutation(
        sample_id,
        transloc_id,
        user,
        service,
        action="mark_false_positive",
        mutate=lambda: service.repository.transloc_handler.mark_false_positive_transloc(
            transloc_id
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive",
    response_model=SampleMutationPayload,
    summary="Remove false-positive flag from translocation",
)
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(
        require_access(permission="manage_translocs", min_role="user", min_level=9)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Remove the false-positive flag from a translocation."""
    return _translocation_mutation(
        sample_id,
        transloc_id,
        user,
        service,
        action="unmark_false_positive",
        mutate=lambda: service.repository.transloc_handler.unmark_false_positive_transloc(
            transloc_id
        ),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Hide translocation comment",
)
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Hide a translocation comment."""
    return _translocation_comment_mutation(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        action="hide",
        mutate=lambda: service.repository.transloc_handler.hide_transloc_comment(
            transloc_id, comment_id
        ),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden",
    response_model=SampleMutationPayload,
    summary="Unhide translocation comment",
)
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
    service: TranslocationService = Depends(get_translocation_service),
):
    """Unhide a translocation comment."""
    return _translocation_comment_mutation(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        action="unhide",
        mutate=lambda: service.repository.transloc_handler.unhide_transloc_comment(
            transloc_id, comment_id
        ),
    )
