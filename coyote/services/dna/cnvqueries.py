"""Service-level DNA CNV query builders."""

from __future__ import annotations


def build_cnv_query(sample_id: str, filters: dict) -> dict:
    """Build a CNV query for a sample based on configured filter criteria."""
    query = {"SAMPLE_ID": sample_id}

    if filters:
        query = {
            "SAMPLE_ID": sample_id,
            "$and": [
                {
                    "$or": [
                        {"NORMAL": {"$ne": 1}},
                        {"NORMAL": {"$exists": False}},
                    ]
                },
                {
                    "$or": [
                        {"ratio": {"$lte": filters["cnv_loss_cutoff"]}},
                        {"ratio": {"$gte": filters["cnv_gain_cutoff"]}},
                    ]
                },
                {
                    "$or": [
                        {
                            "$and": [
                                {"size": {"$gte": filters["min_cnv_size"]}},
                                {"size": {"$lte": filters["max_cnv_size"]}},
                            ]
                        },
                    ]
                },
                {
                    "$or": [
                        {"panel_gene": {"$in": filters.get("filter_genes", [])}},
                        {"panel_gene": {"$exists": False}},
                        {"assay": "tumwgs"},
                    ]
                },
            ],
        }

    return query
