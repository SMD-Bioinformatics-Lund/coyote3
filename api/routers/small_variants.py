"""Canonical DNA and variant router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.contracts.dna import (
    DnaCsvExportContextPayload,
    DnaPlotContextPayload,
    DnaVariantContextPayload,
    DnaVariantsListPayload,
)
from api.contracts.samples import SampleChangePayload
from api.core.dna.dna_filters import get_filter_conseq_terms as _shared_get_filter_conseq_terms
from api.core.dna.dna_variants import get_variant_nomenclature
from api.core.dna.varqueries import build_query
from api.deps.services import get_dna_service, get_resource_annotation_service
from api.extensions import store, util
from api.http import api_error as _api_error
from api.http import get_formatted_assay_config as _get_formatted_assay_config
from api.routers.change_helpers import comment_change, resource_change
from api.runtime_state import app as runtime_app
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.classification.variant_annotation import ResourceAnnotationService
from api.services.common.change_payload import change_payload
from api.services.dna.variant_analysis import DnaService
from api.services.interpretation.annotation_enrichment import (
    add_alt_class as _shared_add_alt_class,
)
from api.services.interpretation.annotation_enrichment import (
    add_global_annotations as _shared_add_global_annotations,
)
from api.services.interpretation.report_summary import (
    create_comment_doc,
    generate_summary_text,
)

router = APIRouter(tags=["small-variants"])


def get_filter_conseq_terms(checked: list[str]) -> list[str]:
    """Resolve filter consequence terms using the active runtime mapping."""
    return _shared_get_filter_conseq_terms(
        checked,
        runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}),
    )


def add_global_annotations(
    variants: list[dict],
    assay_group: str,
    subpanel: str | None,
) -> tuple[list[dict], list[dict]]:
    """Apply shared annotation enrichment using the router-bound annotation handler."""
    return _shared_add_global_annotations(
        variants,
        assay_group,
        subpanel,
        annotation_handler=store.annotation_handler,
    )


def add_alt_class(
    variant: dict,
    assay_group: str,
    subpanel: str | None,
) -> dict:
    """Apply alternative classification enrichment using the router-bound handler."""
    return _shared_add_alt_class(
        variant,
        assay_group,
        subpanel,
        annotation_handler=store.annotation_handler,
    )


@router.get("/api/v1/samples/{sample_id}/small-variants", response_model=DnaVariantsListPayload)
def list_dna_variants(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    """List dna variants.

    Args:
        request (Request): Normalized ``request``.
        sample_id (str): Normalized ``sample_id``.
        user (ApiUser): Normalized ``user``.
        service (DnaService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.list_variants_payload(
            request=request,
            sample=sample,
            util_module=util,
            add_global_annotations_fn=add_global_annotations,
            generate_summary_text_fn=generate_summary_text,
            build_query_fn=build_query,
            get_filter_conseq_terms_fn=get_filter_conseq_terms,
            assay_config_getter=_get_formatted_assay_config,
        )
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/plot-context", response_model=DnaPlotContextPayload
)
def dna_plot_context(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    """Return plot context for DNA variant visualizations.

    Args:
        sample_id (str): Normalized ``sample_id``.
        user (ApiUser): Normalized ``user``.
        service (DnaService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.plot_context_payload(sample=sample, assay_config_getter=_get_formatted_assay_config)
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}", response_model=DnaVariantContextPayload
)
def show_dna_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: DnaService = Depends(get_dna_service),
):
    """Show dna variant.

    Args:
        sample_id (str): Normalized ``sample_id``.
        var_id (str): Normalized ``var_id``.
        user (ApiUser): Normalized ``user``.
        service (DnaService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.variant_context_payload(
            sample=sample,
            var_id=var_id,
            add_alt_class_fn=add_alt_class,
            util_module=util,
            assay_config_getter=_get_formatted_assay_config,
        )
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/exports/snvs/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered SNV CSV export context",
)
def export_snv_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="download_snvs", min_role="user", min_level=9)
    ),
    service: DnaService = Depends(get_dna_service),
):
    """Build SNV export payload (filename + csv content)."""
    sample = _get_sample_for_api(sample_id, user)
    payload = service.list_variants_payload(
        request=request,
        sample=sample,
        util_module=util,
        add_global_annotations_fn=add_global_annotations,
        generate_summary_text_fn=generate_summary_text,
        build_query_fn=build_query,
        get_filter_conseq_terms_fn=get_filter_conseq_terms,
        assay_config_getter=_get_formatted_assay_config,
    )
    variants = payload.get("display_sections_data", {}).get("snvs", [])
    rows = service.build_snv_export_rows(variants=variants)
    content = service.export_rows_to_csv(rows)
    filename = f"{sample.get('name', sample_id)}.filtered.snvs.csv"
    return util.common.convert_to_serializable(
        {"filename": filename, "content": content, "row_count": len(rows)}
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/exports/cnvs/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered CNV CSV export context",
)
def export_cnv_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="download_cnvs", min_role="user", min_level=9)
    ),
    service: DnaService = Depends(get_dna_service),
):
    """Build CNV export payload (filename + csv content)."""
    sample = _get_sample_for_api(sample_id, user)
    payload = service.list_variants_payload(
        request=request,
        sample=sample,
        util_module=util,
        add_global_annotations_fn=add_global_annotations,
        generate_summary_text_fn=generate_summary_text,
        build_query_fn=build_query,
        get_filter_conseq_terms_fn=get_filter_conseq_terms,
        assay_config_getter=_get_formatted_assay_config,
    )
    cnvs = payload.get("display_sections_data", {}).get("cnvs", [])
    assay_group = payload.get("assay_group", "unknown")
    rows = service.build_cnv_export_rows(cnvs=cnvs, sample=sample, assay_group=assay_group)
    content = service.export_rows_to_csv(rows)
    filename = f"{sample.get('name', sample_id)}.filtered.cnvs.csv"
    return util.common.convert_to_serializable(
        {"filename": filename, "content": content, "row_count": len(rows)}
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/exports/translocs/context",
    response_model=DnaCsvExportContextPayload,
    summary="Build filtered translocation CSV export context",
)
def export_transloc_csv_context(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="download_translocs", min_role="user", min_level=9)
    ),
    service: DnaService = Depends(get_dna_service),
):
    """Build translocation export payload (filename + csv content)."""
    sample = _get_sample_for_api(sample_id, user)
    payload = service.list_variants_payload(
        request=request,
        sample=sample,
        util_module=util,
        add_global_annotations_fn=add_global_annotations,
        generate_summary_text_fn=generate_summary_text,
        build_query_fn=build_query,
        get_filter_conseq_terms_fn=get_filter_conseq_terms,
        assay_config_getter=_get_formatted_assay_config,
    )
    translocs = payload.get("display_sections_data", {}).get("translocs", [])
    rows = service.build_transloc_export_rows(translocs=translocs)
    content = service.export_rows_to_csv(rows)
    filename = f"{sample.get('name', sample_id)}.filtered.translocs.csv"
    return util.common.convert_to_serializable(
        {"filename": filename, "content": content, "row_count": len(rows)}
    )


def _require_variant_for_sample(
    sample_id: str, var_id: str, user: ApiUser, service: DnaService
) -> tuple[dict, dict]:
    """Load and validate the target variant for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    variant = service.require_variant_for_sample(sample=sample, var_id=var_id)
    return sample, variant


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from small variant",
)
def unmark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Remove the false-positive flag from a small variant."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="unmark_false_positive",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=False, flag="false_positive"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark small variant false-positive",
)
def mark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Mark a small variant as false positive."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="mark_false_positive",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=True, flag="false_positive"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from small variant",
)
def unmark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Remove the interesting flag from a small variant."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="unmark_interesting",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=False, flag="interesting"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark small variant interesting",
)
def mark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Mark a small variant as interesting."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="mark_interesting",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=True, flag="interesting"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Remove irrelevant flag from small variant",
)
def unmark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Remove the irrelevant flag from a small variant."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="unmark_irrelevant",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=False, flag="irrelevant"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Mark small variant irrelevant",
)
def mark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Mark a small variant as irrelevant."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="mark_irrelevant",
        mutate=lambda: service.set_variant_flag(var_id=var_id, apply=True, flag="irrelevant"),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.post(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/blacklist-entries",
    response_model=SampleChangePayload,
    summary="Create blacklist entry from small variant",
)
def add_variant_to_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Create a blacklist entry from the selected small variant."""
    sample, variant = _require_variant_for_sample(sample_id, var_id, user, service)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    service.blacklist_variant(variant=variant, assay_group=assay_group)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="blacklist",
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/override-blacklist",
    response_model=SampleChangePayload,
    summary="Override blacklist for small variant",
)
def override_variant_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Ignore blacklist status for a single small variant in the current sample."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="override_blacklist",
        mutate=lambda: service.set_variant_override_blacklist(var_id=var_id, override=True),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/override-blacklist",
    response_model=SampleChangePayload,
    summary="Remove blacklist override from small variant",
)
def clear_variant_blacklist_override(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
    service: DnaService = Depends(get_dna_service),
):
    """Remove the blacklist override flag from a single small variant."""
    return resource_change(
        sample_id,
        var_id,
        user,
        service,
        resource="variant",
        action="clear_override_blacklist",
        mutate=lambda: service.set_variant_override_blacklist(var_id=var_id, override=False),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide variant comment",
)
def hide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaService = Depends(get_dna_service),
):
    """Hide a comment on a small variant."""
    return comment_change(
        sample_id,
        var_id,
        comment_id,
        user,
        service,
        resource="variant_comment",
        action="hide",
        mutate=lambda: service.set_variant_comment_hidden(
            var_id=var_id, comment_id=comment_id, hidden=True
        ),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide variant comment",
)
def unhide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
    service: DnaService = Depends(get_dna_service),
):
    """Unhide a comment on a small variant."""
    return comment_change(
        sample_id,
        var_id,
        comment_id,
        user,
        service,
        resource="variant_comment",
        action="unhide",
        mutate=lambda: service.set_variant_comment_hidden(
            var_id=var_id, comment_id=comment_id, hidden=False
        ),
        validate=lambda: _require_variant_for_sample(sample_id, var_id, user, service),
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Bulk false-positive small variant update",
)
def set_variant_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    resource_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    """Set variant false positive bulk.

    Args:
        sample_id (str): Normalized ``sample_id``.
        apply (bool): Normalized ``apply``.
        resource_ids (list[str]): Normalized ``resource_ids``.
        payload (dict): Normalized ``payload``.
        user (ApiUser): Normalized ``user``.
        service (DnaService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    _get_sample_for_api(sample_id, user)
    payload_resource_ids = payload.get("resource_ids") if isinstance(payload, dict) else None
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_resource_ids, list):
        resource_ids = payload_resource_ids
    elif isinstance(payload_variant_ids, list):
        resource_ids = payload_variant_ids
    apply = service.coerce_bool(
        payload.get("apply") if isinstance(payload, dict) else None, default=apply
    )
    service.set_variant_bulk_flag(resource_ids=resource_ids, apply=apply, flag="false_positive")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant_bulk",
            resource_id="bulk",
            action="set_false_positive_bulk",
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Bulk irrelevant small variant update",
)
def set_variant_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    resource_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
    service: DnaService = Depends(get_dna_service),
):
    """Set variant irrelevant bulk.

    Args:
        sample_id (str): Normalized ``sample_id``.
        apply (bool): Normalized ``apply``.
        resource_ids (list[str]): Normalized ``resource_ids``.
        payload (dict): Normalized ``payload``.
        user (ApiUser): Normalized ``user``.
        service (DnaService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    _get_sample_for_api(sample_id, user)
    payload_resource_ids = payload.get("resource_ids") if isinstance(payload, dict) else None
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_resource_ids, list):
        resource_ids = payload_resource_ids
    elif isinstance(payload_variant_ids, list):
        resource_ids = payload_variant_ids
    apply = service.coerce_bool(
        payload.get("apply") if isinstance(payload, dict) else None, default=apply
    )
    service.set_variant_bulk_flag(resource_ids=resource_ids, apply=apply, flag="irrelevant")
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant_bulk",
            resource_id="bulk",
            action="set_irrelevant_bulk",
        )
    )


@router.post(
    "/api/v1/samples/{sample_id}/annotations",
    response_model=SampleChangePayload,
    status_code=201,
    summary="Create sample annotation",
)
def add_variant_comment_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="add_variant_comment", min_role="user", min_level=9)
    ),
    service: ResourceAnnotationService = Depends(get_resource_annotation_service),
):
    """Create a sample annotation on a variant-like resource.

    Args:
        sample_id (str): Normalized ``sample_id``.
        payload (dict): Normalized ``payload``.
        user (ApiUser): Normalized ``user``.
        service (ResourceAnnotationService): Normalized ``service``.

    Returns:
        Normalized return value.
    """
    _get_sample_for_api(sample_id, user)
    target_id = str(payload.get("id", "unknown"))
    form_data = payload.get("form_data", {})
    resource = service.create_annotation(
        form_data=form_data,
        target_id=target_id,
        get_variant_nomenclature_fn=get_variant_nomenclature,
        create_comment_doc_fn=create_comment_doc,
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource=resource,
            resource_id=target_id,
            action="add_comment",
        )
    )
