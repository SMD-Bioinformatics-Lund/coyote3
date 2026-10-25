"""Canonical DNA and variant router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_sample, get_small_variants
from api.interfaces.http.tags import TAG_DNA_VARIANTS
from api.interfaces.http.v1.clinical.common.analysis_query import (
    analysis_query_from_request,
    bulk_flag_values,
)
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.clinical import SmallVariants
from coyote3.application.operations.samples import Sample
from coyote3.contracts.dna import (
    DnaClinPgxPublicPayload,
    DnaCsvExportContextPayload,
    DnaOncoKbPublicPayload,
    DnaPlotContextPayload,
    DnaTieredVariantsPayload,
    DnaTranscriptSelectionRequest,
    DnaVariantContextPayload,
    DnaVariantsListPayload,
)
from coyote3.contracts.samples import SampleChangePayload, SampleCommentSuggestionPayload

router = APIRouter(tags=[TAG_DNA_VARIANTS])


@router.get(
    "/api/v1/samples/{sample_id}/small-variants",
    response_model=DnaVariantsListPayload,
    summary="List sample small variants",
)
def list_dna_variants(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Retrieve SNVs and small indels for an accessible sample.

    Results apply the sample's assay configuration and the active request filters,
    with interpretation annotations attached for review. Access to the sample is
    checked before findings are returned.
    """
    return util.common.convert_to_serializable(service.view(analysis_query_from_request(request)))


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/comment-suggestion",
    response_model=SampleCommentSuggestionPayload,
    summary="Generate a filtered DNA sample-comment suggestion",
)
def dna_sample_comment_suggestion(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return the established DNA summary text for the current sample filters."""
    return util.common.convert_to_serializable(
        service.comment_suggestion(analysis_query_from_request(request))
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/plot-context", response_model=DnaPlotContextPayload
)
def dna_plot_context(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return plot context for DNA variant visualizations.

    \u000c

    Args:
        sample_id: Sample identifier used to load the plot's assay context.
        user: Authenticated user whose sample access is checked before loading data.
        service: Injected DNA service that assembles the plot payload.

    Returns:
        JSON-serializable plot data conforming to DnaPlotContextPayload.
    """
    return util.common.convert_to_serializable(service.plots())


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/tiered",
    response_model=DnaTieredVariantsPayload,
    summary="List selected tiered small variants",
)
def list_tiered_dna_variants(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return all selected tiered small variants for an accessible sample.

    Applies the established sample filters, intent, search, classification scope,
    and tiered-selection exclusion flags. Pagination is not applied. Requires
    sample:view and access to the sample's scope.
    """
    return util.common.convert_to_serializable(
        service.tiered_variants(analysis_query_from_request(request))
    )


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}", response_model=DnaVariantContextPayload
)
def show_dna_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return a small variant's detail context within an accessible sample.

    \u000c

    Args:
        sample_id: Sample identifier used for access checks and assay configuration.
        var_id: Identifier of the variant to display.
        user: Authenticated user whose sample access is checked.
        service: Injected DNA service that assembles the variant detail payload.

    Returns:
        JSON-serializable detail data conforming to DnaVariantContextPayload.
    """
    return util.common.convert_to_serializable(service.context(var_id))


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/oncokb-public",
    response_model=DnaOncoKbPublicPayload,
    summary="Fetch public OncoKB annotation for a small variant",
)
def show_dna_variant_public_oncokb(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return an on-demand public OncoKB API annotation for a small variant."""
    return util.common.convert_to_serializable(service.public_oncokb(var_id))


@router.get(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/clinpgx-public",
    response_model=DnaClinPgxPublicPayload,
    summary="Fetch public ClinPGx gene context for a small variant",
)
def show_dna_variant_public_clinpgx(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Return an on-demand public ClinPGx API gene lookup for a small variant."""
    return util.common.convert_to_serializable(service.public_clinpgx(var_id))


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/selected-transcript",
    response_model=SampleChangePayload,
    summary="Select displayed transcript for a small variant",
)
def select_dna_variant_transcript(
    sample_id: str,
    var_id: str,
    payload: DnaTranscriptSelectionRequest,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Select the transcript used as the primary UI/reporting anchor for a small variant."""
    operation = service.select_transcript(var_id, payload.feature_id)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="select_transcript",
            operation=operation,
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
    user: ApiUser = Depends(require_access(permission="snv:download")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Build SNV export payload (filename + csv content)."""
    return util.common.convert_to_serializable(
        service.export_csv(analysis_query_from_request(request)).model_dump()
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Remove false-positive flag from small variant",
)
def unmark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Remove the false-positive flag from a small variant."""
    operation = service.set_flag(var_id, flag="false_positive", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="unmark_false_positive",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive",
    response_model=SampleChangePayload,
    summary="Mark small variant false-positive",
)
def mark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Mark a small variant as false positive."""
    operation = service.set_flag(var_id, flag="false_positive", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="mark_false_positive",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Remove interesting flag from small variant",
)
def unmark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Remove the interesting flag from a small variant."""
    operation = service.set_flag(var_id, flag="interesting", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="unmark_interesting",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/interesting",
    response_model=SampleChangePayload,
    summary="Mark small variant interesting",
)
def mark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Mark a small variant as interesting."""
    operation = service.set_flag(var_id, flag="interesting", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="mark_interesting",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Remove irrelevant flag from small variant",
)
def unmark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Remove the irrelevant flag from a small variant."""
    operation = service.set_flag(var_id, flag="irrelevant", value=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="unmark_irrelevant",
            operation=operation,
        )
    )


@router.patch(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/irrelevant",
    response_model=SampleChangePayload,
    summary="Mark small variant irrelevant",
)
def mark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Mark a small variant as irrelevant."""
    operation = service.set_flag(var_id, flag="irrelevant", value=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="mark_irrelevant",
            operation=operation,
        )
    )


@router.post(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/blacklist-entries",
    response_model=SampleChangePayload,
    summary="Create blacklist entry from small variant",
)
def add_variant_to_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Create a blacklist entry from the selected small variant."""
    operation = service.add_to_blacklist(var_id)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="blacklist",
            operation=operation,
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
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Ignore blacklist status for a single small variant in the current sample."""
    operation = service.override_blacklist(var_id, override=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="override_blacklist",
            operation=operation,
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/override-blacklist",
    response_model=SampleChangePayload,
    summary="Remove blacklist override from small variant",
)
def clear_variant_blacklist_override(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Remove the blacklist override flag from a single small variant."""
    operation = service.override_blacklist(var_id, override=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant",
            resource_id=var_id,
            action="clear_override_blacklist",
            operation=operation,
        )
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
    user: ApiUser = Depends(require_access(permission="variant.comment:hide")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Hide a comment on a small variant."""
    service.set_comment_hidden(var_id, comment_id, hidden=True)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="variant_comment", resource_id=comment_id, action="hide"
        )
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
    user: ApiUser = Depends(require_access(permission="variant.comment:unhide")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Unhide a comment on a small variant."""
    service.set_comment_hidden(var_id, comment_id, hidden=False)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource="variant_comment", resource_id=comment_id, action="unhide"
        )
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
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Apply or remove the false-positive flag on selected small variants.

    \u000c

    Args:
        sample_id: Sample identifier used for access checks and the change response.
        apply: Whether to set the flag; defaults to True unless overridden in the body.
        resource_ids: Query-supplied variant identifiers when the body supplies no list.
        payload: Optional body with resource_ids (preferred), variant_ids, and apply.
        user: Authenticated user with snv:manage permission and sample access.
        service: Injected DNA service that updates variant flags.

    Returns:
        SampleChangePayload-compatible data describing the bulk flag operation.
    """
    resource_ids, apply = bulk_flag_values(payload, resource_ids, apply)
    operation = service.set_bulk_flags(resource_ids, flag="false_positive", value=apply)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant_bulk",
            resource_id="bulk",
            action="set_false_positive_bulk",
            operation=operation,
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
    user: ApiUser = Depends(require_access(permission="snv:manage")),
    service: SmallVariants = Depends(get_small_variants),
):
    """Apply or remove the irrelevant flag on selected small variants.

    \u000c

    Args:
        sample_id: Sample identifier used for access checks and the change response.
        apply: Whether to set the flag; defaults to True unless overridden in the body.
        resource_ids: Query-supplied variant identifiers when the body supplies no list.
        payload: Optional body with resource_ids (preferred), variant_ids, and apply.
        user: Authenticated user with snv:manage permission and sample access.
        service: Injected DNA service that updates variant flags.

    Returns:
        SampleChangePayload-compatible data describing the bulk flag operation.
    """
    resource_ids, apply = bulk_flag_values(payload, resource_ids, apply)
    operation = service.set_bulk_flags(resource_ids, flag="irrelevant", value=apply)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="variant_bulk",
            resource_id="bulk",
            action="set_irrelevant_bulk",
            operation=operation,
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
    user: ApiUser = Depends(require_access(permission="variant.comment:add:own")),
    service: Sample = Depends(get_sample),
):
    """Create a sample annotation on a variant-like resource.

    \u000c

    Args:
        sample_id: Sample identifier used for access checks and the change response.
        payload: Annotation target in id and comment fields in form_data.
        user: Authenticated user with variant.comment:add:own permission; global annotations
            additionally require variant.comment:add:global.
        service: Injected service responsible for creating the annotation.

    Returns:
        SampleChangePayload-compatible data identifying the annotated resource.
    """
    target_id = str(payload.get("id", "unknown"))
    resource = service.add_annotation(target_id, payload.get("form_data", {}))
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id, resource=resource, resource_id=target_id, action="add_comment"
        )
    )
