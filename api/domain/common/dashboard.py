"""Dashboard payload shaping helpers."""

from __future__ import annotations

from collections import defaultdict

PANEL_ASP_FAMILIES = frozenset({"panel", "panel-dna", "panel-rna"})


def _asp_gene_stats_rows(data: dict | list | None) -> list[dict]:
    """Normalize repository results into dashboard-ready ASP rows."""
    if isinstance(data, dict):
        iterable = data.values()
    else:
        iterable = data or []
    return [dict(doc) for doc in iterable]


def is_panel_asp(details: dict) -> bool:
    """Return whether an ASP belongs to a targeted panel family."""
    family = str(details.get("asp_family") or "").strip().lower()
    return family in PANEL_ASP_FAMILIES


def format_asp_gene_stats(data: dict | list | None) -> dict:
    """Group assay-panel gene counts by assay group."""
    result = {}
    for doc_dict in _asp_gene_stats_rows(data):
        key = doc_dict.pop("_id", None)
        result[key or len(result)] = doc_dict

    grouped = defaultdict(list)
    for _assay_id, details in result.items():
        group = details.get("asp_group", "Unknown")
        grouped[group].append(details)
    return dict(grouped)


def format_panel_gene_stats(data: dict | list | None) -> dict:
    """Group active targeted-panel gene counts while excluding WGS and WTS ASPs."""
    return format_asp_gene_stats([row for row in _asp_gene_stats_rows(data) if is_panel_asp(row)])


def panel_asp_ids(data: dict | list | None) -> list[str]:
    """Return normalized active targeted-panel identifiers."""
    return sorted(
        {
            str(row.get("asp_id") or "").strip()
            for row in _asp_gene_stats_rows(data)
            if is_panel_asp(row) and str(row.get("asp_id") or "").strip()
        }
    )


def summarize_panel_gene_stats(data: dict | list | None) -> dict[str, int]:
    """Summarize the active targeted-panel portfolio for dashboard cards."""
    rows = [row for row in _asp_gene_stats_rows(data) if is_panel_asp(row)]
    return {
        "active_panels": len(rows),
        "assay_groups": len(
            {
                str(row.get("asp_group") or "").strip().lower()
                for row in rows
                if str(row.get("asp_group") or "").strip()
            }
        ),
        "covered_gene_assignments": sum(
            int(row.get("covered_genes_count", 0) or 0) for row in rows
        ),
        "germline_gene_assignments": sum(
            int(row.get("germline_genes_count", 0) or 0) for row in rows
        ),
        "accredited_panels": sum(1 for row in rows if row.get("accredited") is True),
    }
