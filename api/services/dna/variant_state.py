"""State-changing and lookup helpers for DNA variant workflows."""

from __future__ import annotations

from api.core.dna.cnvqueries import build_cnv_query
from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.http import api_error


def load_cnvs_for_sample(
    service, *, sample: dict, sample_filters: dict, filter_genes: list[str]
) -> list[dict]:
    """Load CNVs for a sample using the active filters."""
    cnv_query = build_cnv_query(
        str(sample["_id"]),
        filters={**sample_filters, "filter_genes": filter_genes},
    )
    cnvs = list(service.copy_number_variant_handler.get_sample_cnvs(cnv_query))
    filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
    if filter_cnveffects:
        cnvs = cnvtype_variant(cnvs, filter_cnveffects)
    return cnv_organizegenes(cnvs)


def require_variant_for_sample(service, *, sample: dict, var_id: str) -> dict:
    """Load a variant and assert it belongs to the provided sample."""
    variant = service.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise api_error(404, "Variant not found for sample")
    return variant


def set_variant_bulk_flag(service, *, resource_ids: list[str], apply: bool, flag: str) -> None:
    """Apply or remove a bulk boolean flag on variants."""
    if not resource_ids:
        return
    if flag == "false_positive":
        if apply:
            service.variant_handler.mark_false_positive_var_bulk(resource_ids)
        else:
            service.variant_handler.unmark_false_positive_var_bulk(resource_ids)
        return
    if flag == "irrelevant":
        if apply:
            service.variant_handler.mark_irrelevant_var_bulk(resource_ids)
        else:
            service.variant_handler.unmark_irrelevant_var_bulk(resource_ids)
        return
    raise ValueError(f"Unsupported flag: {flag}")


def set_variant_flag(service, *, var_id: str, apply: bool, flag: str) -> None:
    """Apply or remove a boolean flag on a single variant."""
    if flag == "false_positive":
        if apply:
            service.variant_handler.mark_false_positive_var(var_id)
        else:
            service.variant_handler.unmark_false_positive_var(var_id)
        return
    if flag == "interesting":
        if apply:
            service.variant_handler.mark_interesting_var(var_id)
        else:
            service.variant_handler.unmark_interesting_var(var_id)
        return
    if flag == "irrelevant":
        if apply:
            service.variant_handler.mark_irrelevant_var(var_id)
        else:
            service.variant_handler.unmark_irrelevant_var(var_id)
        return
    raise ValueError(f"Unsupported flag: {flag}")


def blacklist_variant(service, *, variant: dict[str, str], assay_group: str) -> None:
    """Create a blacklist entry for a variant in an assay group."""
    service.blacklist_handler.blacklist_variant(variant, assay_group)


def set_variant_override_blacklist(service, *, var_id: str, override: bool) -> None:
    """Apply or remove the blacklist-override flag on a variant."""
    service.variant_handler.set_override_blacklist(var_id, override)


def set_variant_comment_hidden(service, *, var_id: str, comment_id: str, hidden: bool) -> None:
    """Hide or unhide a variant comment."""
    if hidden:
        service.variant_handler.hide_var_comment(var_id, comment_id)
        return
    service.variant_handler.unhide_variant_comment(var_id, comment_id)


def coerce_bool(value: object, default: bool = True) -> bool:
    """Convert arbitrary input into a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default
