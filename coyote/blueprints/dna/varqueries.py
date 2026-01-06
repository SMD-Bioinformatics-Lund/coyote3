#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
This module is part of the Coyote3 codebase and provides query-building utilities for genomic data analysis.
It defines functions to construct MongoDB queries for different analysis types (e.g., myeloid, solid, swea)
based on user-provided settings, such as frequency thresholds, depth, gene filters, and variant consequences.
"""

import re


def build_query(assay_group: str, settings: dict) -> dict:
    """
    Constructs a MongoDB query dictionary for genomic variant analysis based on the analysis type and user settings.

    Args:
        assay_group (str): The analysis type (e.g., "myeloid", "solid", "swea", etc.).
        settings (dict): User-provided settings including frequency thresholds, depth, gene filters, and variant consequences.

    Returns:
        dict: A MongoDB query dictionary tailored to the specified analysis type and settings.
    """

    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    gene_pos_filter = build_pos_genes_filter(settings)

    # Myeloid requires settings: min_freq, min_depth, min_alt_reads, max_control_freq, filter_conseq(list)

    if assay_group in {"myeloid", "hematology", "tumwgs", "unknown"}:
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,  # gene_pos_filter
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
                                # Case sample fulfills filter critieria
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
                                # Either control sample fulfills criteria, or there is no control sample (unpaired tumor sample)
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
                                # Filters if gnomad population frequency are above the max_popfreq
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
                                # Either variant fullfills Consequence-filter or is a structural variant in FLT3.
                                {
                                    "$or": [
                                        {
                                            "INFO.selected_CSQ.Consequence": {
                                                "$in": settings["filter_conseq"]
                                            }
                                        },
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {
                                                        "$in": settings["filter_conseq"]
                                                    }
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
                # Case sample fulfills filter critieria
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
                # Either variant fullfills Consequence-filter or is a structural variant in FLT3.
                {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": settings["filter_conseq"]}}}},
            ],
        }

    if assay_group == "solid":
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,  # gene_pos_filter
                {
                    "$or": [
                        {"FILTER": {"$in": ["GERMLINE"]}},
                        {
                            "$and": [
                                # Case sample fulfills filter critieria
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
                                # Either control sample fulfills criteria, or there is no control sample (unpaired tumor sample)
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
                                # Filters if gnomad population frequency are above the max_popfreq
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
                                # Either variant fullfills Consequence-filter or is a promoter variant in TERT.
                                {
                                    "$or": [
                                        {
                                            "INFO.selected_CSQ.Consequence": {
                                                "$in": settings["filter_conseq"]
                                            }
                                        },
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {
                                                        "$in": settings["filter_conseq"]
                                                    }
                                                }
                                            }
                                        },
                                        {
                                            "$and": [
                                                {
                                                    "$or": [
                                                        {
                                                            "genes": {
                                                                "$in": [
                                                                    "TERT",
                                                                    "NFKBIE",
                                                                ]
                                                            }
                                                        },
                                                    ]
                                                },
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
    """
    Constructs a partial MongoDB query for filtering variants by position, gene, and optional flags.

    Args:
        settings (dict): User-provided settings that may include:
            - disp_pos (list): List of positions to filter on.
            - filter_genes (list): List of gene symbols to filter on.
            - fp (str): Optional flag for filtering.
            - irrelevant (str): Optional flag for filtering.

    Returns:
        dict: A partial MongoDB query dictionary for use in variant queries.
    """
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])
    fp = settings.get("fp", "")
    irrelevant = settings.get("irrelevant", "")

    partial_query = {}

    if pos_list:
        partial_query["POS"] = {"$in": pos_list}
    elif genes_list:
        partial_query["genes"] = {"$in": genes_list}
    else:
        pass

    if fp:
        partial_query["fp"] = fp

    if irrelevant:
        partial_query["irrelevant"] = irrelevant

    if partial_query:
        return {"$and": [partial_query]}
    else:
        return {}
