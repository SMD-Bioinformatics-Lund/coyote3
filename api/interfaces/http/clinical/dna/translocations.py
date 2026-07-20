"""Canonical translocation router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.app.container import store, util
from api.app.deps.services import get_dna_service, get_dna_structural_service
from api.app.http import get_formatted_assay_config as _get_formatted_assay_config
from api.application.dna.structural_variants import DnaStructuralService
from api.application.dna.variant_analysis import DnaService
from api.application.interpretation.annotation_enrichment import (
    add_global_annotations as _shared_add_global_annotations,
)
from api.application.interpretation.report_summary import generate_summary_text
from api.contracts.dna import (
    DnaCsvExportContextPayload,
    DnaTranslocationContextPayload,
    DnaTranslocationsPayload,
)
from api.contracts.samples import SampleChangePayload
from api.domain.core.dna.dna_filters import (
    get_filter_conseq_terms as _shared_get_filter_conseq_terms,
)
from api.domain.core.dna.varqueries import build_query
from api.interfaces.http.clinical.common.change_helpers import comment_change, resource_change
from api.interfaces.http.tags import TAG_STRUCTURAL_VARIANTS
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=[TAG_STRUCTURAL_VARIANTS])


def _get_filter_conseq_terms(checked: list[str], vep_version: str | int | None = None) -> list[str]:
    """Resolve filter consequence terms using grouped VEP metadata from Mongo."""
    return _shared_get_filter_conseq_terms(
        checked,
        store.vep_metadata_repository.get_consequence_group_map(
            None if vep_version is None else str(vep_version)
        ),
    )


def _add_global_annotations(
    variants: list[dict],
    assay_group: str,
    subpanel: str | None,
) -> tuple[list[dict], list[dict]]:
    """Apply shared annotation enrichment for export-context construction."""
    return _shared_add_global_annotations(
        variants,
        assay_group,
        subpanel,
        annotation_repository=store.annotation_repository,
    )


@router.get("/api/v1/samples/{sample_id}/translocations", response_model=DnaTranslocationsPayload)
def list_dna_translocations(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return translocations for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_translocations_payload(request=request, sample=sample)
    )


@router.get(
    "/api/v1/samples/{sample_id}/translocations/exports/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered translocation CSV export context",
)
def export_transloc_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:download")),
    service: DnaService = Depends(get_dna_service),
):
    """Build translocation export payload from the sample's active filters."""
    sample = _get_sample_for_api(sample_id, user)
    payload = service.list_variants_payload(
        request=request,
        sample=sample,
        util_module=util,
        add_global_annotations_fn=_add_global_annotations,
        generate_summary_text_fn=generate_summary_text,
        build_query_fn=build_query,
        get_filter_conseq_terms_fn=lambda values: _get_filter_conseq_terms(
            values, sample.get("vep_version")
        ),
        assay_config_getter=_get_formatted_assay_config,
        paginate=False,
    )
    translocs = payload.get("display_sections_data", {}).get("translocs", [])
    rows = service.build_transloc_export_rows(translocs=translocs)
    content = service.export_rows_to_csv(rows)
    filename = f"{sample.get('name', sample_id)}.filtered.translocs.csv"
    return util.common.convert_to_serializable(
        {"filename": filename, "content": content, "row_count": len(rows)}
    )


@router.get(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}",
    response_model=DnaTranslocationContextPayload,
)
def show_dna_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access()),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return translocation detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_translocation_payload(sample=sample, transloc_id=transloc_id, util_module=util)
    )


@router.patch(
    "/api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark translocation interesting",
)
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="translocation:manage")),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a translocation as interesting."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="mark_interesting",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=True, flag="interesting"
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the interesting flag from a translocation."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="unmark_interesting",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=False, flag="interesting"
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a translocation as false positive."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="mark_false_positive",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=True, flag="false_positive"
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the false-positive flag from a translocation."""
    return resource_change(
        sample_id,
        transloc_id,
        user,
        service,
        resource="translocation",
        action="unmark_false_positive",
        mutate=lambda: service.set_translocation_flag(
            transloc_id=transloc_id, apply=False, flag="false_positive"
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Hide a translocation comment."""
    return comment_change(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        resource="translocation_comment",
        action="hide",
        mutate=lambda: service.set_translocation_comment_hidden(
            transloc_id=transloc_id, comment_id=comment_id, hidden=True
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Unhide a translocation comment."""
    return comment_change(
        sample_id,
        transloc_id,
        comment_id,
        user,
        service,
        resource="translocation_comment",
        action="unhide",
        mutate=lambda: service.set_translocation_comment_hidden(
            transloc_id=transloc_id, comment_id=comment_id, hidden=False
        ),
    )
