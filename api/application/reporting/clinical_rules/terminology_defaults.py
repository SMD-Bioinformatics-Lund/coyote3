"""Canonical default terminology fragments for rule renderers and migration."""

from __future__ import annotations

from typing import Any

from api.domain.common.reporting import STANDARD_TIER_SUMMARY_PHRASES

DNA_TERMINOLOGY: dict[str, Any] = {
    "paired_text": (
        "Analysen avser somatiska mutationer (hudbiopsi har använts som kontrollmaterial). "
    ),
    "list_singular": "Analysen omfattar genlistan: ",
    "list_plural": "Analysen omfattar genlistorna: ",
    "conjunction": "samt",
    "gene_singular": " som innefattar genen: ",
    "gene_plural": " som innefattar generna: ",
    "gene_conjunction": "samt",
    "gene_count_prefix": " som innefattar ",
    "gene_count_suffix": " gener",
    "gene_list_limit": 20,
    "list_suffix": ". ",
    "germline_prefix": "För ",
    "germline_conjunction": "samt",
    "germline_suffix": " undersöks även konstitutionella mutationer.",
}


FUSION_TERMINOLOGY: dict[str, Any] = {
    "tier_labels": {
        "1": "stark klinisk signifikans (Tier I)",
        "2": "potentiell klinisk signifikans (Tier II)",
        "3": "oklar klinisk signifikans (Tier III)",
    },
    "first_lead": "Vid analysen finner man",
    "next_lead": "Vidare finner man",
    "tier_prefix": " en fusion av ",
    "genes_prefix": " mellan generna ",
    "gene_joiner": " och ",
    "sentence_suffix": ".",
    "breakpoint_prefix": " De genomiska positionerna för brottspunkterna är ",
    "breakpoint_joiner": " och ",
    "breakpoint_suffix": ".",
    "support_prefix": "Rearrangemanget är påvisat efter manuell eftergranskning av data där ",
    "support_middle": " läspar, och  läsningar direkt över brottspunkten ger stöd för en ",
    "support_genes_prefix": "",
    "support_gene_joiner": "::",
    "support_suffix": "-genfusion.",
}


def build_default_terminology() -> dict[str, Any]:
    """Return the complete default terminology shape used for migration and tests."""
    return {
        "tier_summary": STANDARD_TIER_SUMMARY_PHRASES,
        "dna_report_intro": {**DNA_TERMINOLOGY, "base_text": ""},
        "fusion_summary": FUSION_TERMINOLOGY,
    }
