"""Dashboard payload shaping helpers."""

from __future__ import annotations

from collections import defaultdict


def format_asp_gene_stats(data: dict) -> dict:
    """Group assay-panel gene counts by assay group."""
    if isinstance(data, dict):
        iterable = data.values()
    else:
        iterable = data or []
    result = {}
    for doc in iterable:
        doc_dict = dict(doc)
        key = doc_dict.pop("_id", None)
        result[key or len(result)] = doc_dict

    grouped = defaultdict(list)
    for _assay_id, details in result.items():
        group = details.get("asp_group", "Unknown")
        grouped[group].append(details)
    return dict(grouped)
