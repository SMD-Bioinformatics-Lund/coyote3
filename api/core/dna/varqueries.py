"""Service-level DNA SNV query builders."""

from __future__ import annotations

import re


def build_query(assay_group: str, settings: dict) -> dict:
    """Construct a MongoDB SNV query from assay group and filter settings."""
    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    gene_pos_filter = build_pos_genes_filter(settings)

    query: dict = {"SAMPLE_ID": settings["id"]}

    if assay_group in {"myeloid", "hematology", "tumwgs", "unknown"}:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                {
                    "$or": [
                        {"INFO.MYELOID_GERMLINE": 1},
                        {
                            "FILTER": {"$in": ["GERMLINE"]},
                            "INFO.CSQ": {"$elemMatch": {"SYMBOL": "CEBPA"}},
                        },
                        {
                            "$and": [
                                {"POS": {"$gt": 115256520}},
                                {"POS": {"$lt": 115256538}},
                                {"CHROM": 1},
                            ]
                        },
                        {
                            "$and": [
                                {
                                    "GT": {
                                        "$elemMatch": {
                                            "type": "case",
                                            "AF": {
                                                "$gte": float(settings["min_freq"]),
                                                "$lte": float(settings["max_freq"]),
                                            },
                                            "DP": {"$gte": float(settings["min_depth"])},
                                            "VD": {"$gte": float(settings["min_alt_reads"])},
                                        }
                                    }
                                },
                                {
                                    "$or": [
                                        {
                                            "GT": {
                                                "$elemMatch": {
                                                    "type": "control",
                                                    "AF": {
                                                        "$lte": float(settings["max_control_freq"])
                                                    },
                                                    "DP": {"$gte": float(settings["min_depth"])},
                                                }
                                            }
                                        },
                                        {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
                                    ]
                                },
                                {
                                    "$or": [
                                        {
                                            "gnomad_frequency": {
                                                "$exists": True,
                                                "$type": "number",
                                                "$lte": float(settings["max_popfreq"]),
                                            }
                                        },
                                        {"gnomad_frequency": {"$type": "string"}},
                                        {"gnomad_frequency": None},
                                        {"gnomad_frequency": {"$exists": False}},
                                    ]
                                },
                                {
                                    "$or": [
                                        {"INFO.selected_CSQ.Consequence": {"$in": settings["filter_conseq"]}},
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {"$in": settings["filter_conseq"]}
                                                }
                                            }
                                        },
                                        {
                                            "$and": [
                                                {"genes": {"$in": ["FLT3"]}},
                                                {
                                                    "$or": [
                                                        {"INFO.SVTYPE": {"$exists": "true"}},
                                                        {"ALT": large_ins_regex},
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ],
                },
            ],
        }

    if assay_group in ["swea", "gmsonco"]:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                {
                    "GT": {
                        "$elemMatch": {
                            "AF": {
                                "$gte": float(settings["min_freq"]),
                                "$lte": float(settings["max_freq"]),
                            },
                            "DP": {"$gte": float(settings["min_depth"])},
                            "VD": {"$gte": float(settings["min_alt_reads"])},
                        }
                    }
                },
                {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": settings["filter_conseq"]}}}},
            ],
        }

    if assay_group == "solid":
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
                {
                    "$or": [
                        {"FILTER": {"$in": ["GERMLINE"]}},
                        {
                            "$and": [
                                {
                                    "GT": {
                                        "$elemMatch": {
                                            "type": "case",
                                            "AF": {
                                                "$gte": float(settings["min_freq"]),
                                                "$lte": float(settings["max_freq"]),
                                            },
                                            "DP": {"$gte": float(settings["min_depth"])},
                                            "VD": {"$gte": float(settings["min_alt_reads"])},
                                        }
                                    }
                                },
                                {
                                    "$or": [
                                        {
                                            "GT": {
                                                "$elemMatch": {
                                                    "type": "control",
                                                    "AF": {
                                                        "$lte": float(settings["max_control_freq"])
                                                    },
                                                    "DP": {"$gte": float(settings["min_depth"])},
                                                }
                                            }
                                        },
                                        {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
                                    ]
                                },
                                {
                                    "$or": [
                                        {
                                            "gnomad_frequency": {
                                                "$exists": True,
                                                "$type": "number",
                                                "$lte": float(settings["max_popfreq"]),
                                            }
                                        },
                                        {"gnomad_frequency": {"$type": "string"}},
                                        {"gnomad_frequency": None},
                                        {"gnomad_frequency": {"$exists": False}},
                                    ]
                                },
                                {
                                    "$or": [
                                        {"INFO.selected_CSQ.Consequence": {"$in": settings["filter_conseq"]}},
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {"$in": settings["filter_conseq"]}
                                                }
                                            }
                                        },
                                        {
                                            "$and": [
                                                {"$or": [{"genes": {"$in": ["TERT", "NFKBIE"]}}]},
                                                {
                                                    "$or": [
                                                        {
                                                            "INFO.selected_CSQ.Consequence": {
                                                                "$in": [
                                                                    "regulatory_region_variant",
                                                                    "TF_binding_site_variant",
                                                                ]
                                                            }
                                                        },
                                                        {
                                                            "INFO.CSQ": {
                                                                "$elemMatch": {
                                                                    "Consequence": {
                                                                        "$in": [
                                                                            "regulatory_region_variant",
                                                                            "TF_binding_site_variant",
                                                                        ]
                                                                    }
                                                                }
                                                            }
                                                        },
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ],
                },
            ],
        }

    return query


def build_pos_genes_filter(settings: dict) -> dict:
    """Build optional POS/gene/fp/irrelevant partial filters."""
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])
    fp = settings.get("fp", "")
    irrelevant = settings.get("irrelevant", "")

    partial_query = {}

    if pos_list:
        partial_query["POS"] = {"$in": pos_list}
    elif genes_list:
        partial_query["genes"] = {"$in": genes_list}

    if fp:
        partial_query["fp"] = fp

    if irrelevant:
        partial_query["irrelevant"] = irrelevant

    if partial_query:
        return {"$and": [partial_query]}
    return {}
