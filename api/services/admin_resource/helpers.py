"""Shared helpers and constants for admin resource services."""

from __future__ import annotations

from typing import Any

from api.contracts.schemas import normalize_collection_document
from api.http import api_error


def _normalize_asp_category(value: Any) -> str:
    """Normalize ASP category labels to managed DNA/RNA categories."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "DNA",
        "somatic": "DNA",
        "rna": "RNA",
    }
    return mapping.get(raw, str(value or "").strip().upper() or "DNA")


def _normalize_asp_category_doc(value: Any) -> str:
    """Normalize ASP category labels for persisted document payloads."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "dna",
        "somatic": "dna",
        "rna": "rna",
    }
    return mapping.get(raw, raw or "dna")


_DEPRECATED_SNV_FILTER_KEYS: tuple[str, ...] = (
    "snv_mode",
    "snv_require_case_gt_type",
    "snv_enable_control_guard",
    "snv_enable_popfreq_guard",
    "snv_enable_consequence_guard",
    "snv_allow_germline_escape",
    "snv_allow_cebpa_germline_escape",
    "snv_allow_flt3_large_indel_escape",
    "snv_allow_tert_nfkbie_regulatory_escape",
    "snv_gene_region_allow",
    "snv_gene_consequence_allow",
    "cnv_mode",
    "cnv_enable_normal_guard",
    "cnv_enable_ratio_guard",
    "cnv_enable_size_guard",
    "cnv_enable_panel_gene_guard",
    "fusion_mode",
    "fusion_enable_callers_guard",
    "fusion_enable_effects_guard",
    "fusion_enable_spanning_guard",
    "fusion_enable_gene_scope_guard",
    "fusion_enable_desc_guard",
)


def _sanitize_aspc_filters(config: dict[str, Any]) -> None:
    """Remove deprecated filter keys from an ASPC config dict in-place."""
    filters = config.get("filters")
    if not isinstance(filters, dict):
        return
    for key in _DEPRECATED_SNV_FILTER_KEYS:
        filters.pop(key, None)


def _validated_doc(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalize payload using collection Pydantic contract."""
    try:
        return normalize_collection_document(collection, payload)
    except Exception as exc:
        raise api_error(400, f"Invalid {collection} payload: {exc}") from exc
