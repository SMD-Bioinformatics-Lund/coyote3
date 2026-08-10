"""Canonical CNV router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.app import http
from api.app.container import store, util
from api.app.deps.services import get_dna_service, get_dna_structural_service
from api.application.dna.structural_variants import DnaStructuralService
from api.application.dna.variant_analysis import DnaService
from api.application.interpretation import annotation_enrichment
from api.application.interpretation.report_summary import generate_summary_text
from api.config.database_versions import require_sample_vep_version
from api.contracts.dna import DnaCnvContextPayload, DnaCnvListPayload, DnaCsvExportContextPayload
from api.contracts.samples import SampleChangePayload
from api.domain.core.dna import dna_filters
from api.domain.core.dna.varqueries import build_query
from api.interfaces.http.clinical.common.change_helpers import comment_change, resource_change
from api.interfaces.http.tags import TAG_DNA_CNV
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=[TAG_DNA_CNV])


def _get_filter_conseq_terms(checked: list[str], vep_version: str | int | None = None) -> list[str]:
    """Resolve filter consequence terms using grouped VEP metadata from Mongo."""
    return dna_filters.get_filter_conseq_terms(
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
    return annotation_enrichment.add_global_annotations(
        variants,
        assay_group,
        subpanel,
        annotation_repository=store.annotation_repository,
    )


@router.get("/api/v1/samples/{sample_id}/cnvs", response_model=DnaCnvListPayload)
def list_dna_cnvs(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return CNVs for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_cnvs_payload(request=request, sample=sample, util_module=util)
    )


@router.get(
    "/api/v1/samples/{sample_id}/cnvs/exports/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered CNV CSV export context",
)
def export_cnv_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:download")),
    service: DnaService = Depends(get_dna_service),
):
    """Build CNV export payload from the sample's active CNV filters."""
    sample = _get_sample_for_api(sample_id, user)
    payload = service.list_variants_payload(
        request=request,
        sample=sample,
        util_module=util,
        add_global_annotations_fn=_add_global_annotations,
        generate_summary_text_fn=generate_summary_text,
        build_query_fn=build_query,
        get_filter_conseq_terms_fn=lambda values: _get_filter_conseq_terms(
            values, require_sample_vep_version(sample)
        ),
        assay_config_getter=http.get_formatted_assay_config,
        paginate=False,
    )
    cnvs = payload.get("display_sections_data", {}).get("cnvs", [])
    assay_group = payload.get("assay_group", "unknown")
    rows = service.build_cnv_export_rows(cnvs=cnvs, sample=sample, assay_group=assay_group)
    content = service.export_rows_to_csv(rows)
    filename = f"{sample.get('name', sample_id)}.filtered.cnvs.csv"
    return util.common.convert_to_serializable(
        {"filename": filename, "content": content, "row_count": len(rows)}
    )


@router.get("/api/v1/samples/{sample_id}/cnvs/{cnv_id}", response_model=DnaCnvContextPayload)
def show_dna_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access()),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Return CNV detail payload."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.show_cnv_payload(sample=sample, cnv_id=cnv_id, util_module=util)
    )


@router.delete(
    "/api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from CNV",
)
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="cnv:manage")),
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the interesting flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_interesting",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="interesting"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as interesting."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_interesting",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="interesting"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as false positive."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_false_positive",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="false_positive"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the false-positive flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_false_positive",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="false_positive"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Mark a CNV as noteworthy."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="mark_noteworthy",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=True, flag="noteworthy"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Remove the noteworthy flag from a CNV."""
    return resource_change(
        sample_id,
        cnv_id,
        user,
        service,
        resource="cnv",
        action="unmark_noteworthy",
        mutate=lambda: service.set_cnv_flag(cnv_id=cnv_id, apply=False, flag="noteworthy"),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Hide a CNV comment."""
    return comment_change(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        resource="cnv_comment",
        action="hide",
        mutate=lambda: service.set_cnv_comment_hidden(
            cnv_id=cnv_id, comment_id=comment_id, hidden=True
        ),
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
    service: DnaStructuralService = Depends(get_dna_structural_service),
):
    """Unhide a CNV comment."""
    return comment_change(
        sample_id,
        cnv_id,
        comment_id,
        user,
        service,
        resource="cnv_comment",
        action="unhide",
        mutate=lambda: service.set_cnv_comment_hidden(
            cnv_id=cnv_id, comment_id=comment_id, hidden=False
        ),
    )
