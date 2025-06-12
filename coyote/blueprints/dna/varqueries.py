import re


def build_query(which, settings):

    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    gene_pos_filter = build_pos_genes_filter(settings)

    # Myeloid requires settings: min_freq, min_depth, min_alt_reads, max_control_freq, filter_conseq(list)

    if which in {"myeloid", "hematology", "fusion", "tumwgs", "unknown"}:
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
                                                "$gte": float(
                                                    settings["min_freq"]
                                                ),
                                                "$lte": float(
                                                    settings["max_freq"]
                                                ),
                                            },
                                            "DP": {
                                                "$gte": float(
                                                    settings["min_depth"]
                                                )
                                            },
                                            "VD": {
                                                "$gte": float(
                                                    settings["min_alt_reads"]
                                                )
                                            },
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
                                                        "$lte": float(
                                                            settings[
                                                                "max_control_freq"
                                                            ]
                                                        )
                                                    },
                                                    "DP": {
                                                        "$gte": float(
                                                            settings[
                                                                "min_depth"
                                                            ]
                                                        )
                                                    },
                                                }
                                            }
                                        },
                                        {
                                            "GT": {
                                                "$not": {
                                                    "$elemMatch": {
                                                        "type": "control"
                                                    }
                                                }
                                            }
                                        },
                                    ]
                                },
                                # Filters if gnomad population frequency are above the max_popfreq
                                {
                                    "$or": [
                                        {
                                            "gnomad_frequency": {
                                                "$exists": True,
                                                "$type": "number",
                                                "$lte": float(
                                                    settings["max_popfreq"]
                                                ),
                                            }
                                        },
                                        {
                                            "gnomad_frequency": {
                                                "$type": "string"
                                            }
                                        },
                                        {"gnomad_frequency": None},
                                        {
                                            "gnomad_frequency": {
                                                "$exists": False
                                            }
                                        },
                                    ]
                                },
                                # Either variant fullfills Consequence-filter or is a structural variant in FLT3.
                                {
                                    "$or": [
                                        {
                                            "INFO.selected_CSQ.Consequence": {
                                                "$in": settings[
                                                    "filter_conseq"
                                                ]
                                            }
                                        },
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {
                                                        "$in": settings[
                                                            "filter_conseq"
                                                        ]
                                                    }
                                                }
                                            }
                                        },
                                        {
                                            "$and": [
                                                {"genes": {"$in": ["FLT3"]}},
                                                {
                                                    "$or": [
                                                        {
                                                            "INFO.SVTYPE": {
                                                                "$exists": "true"
                                                            }
                                                        },
                                                        {
                                                            "ALT": large_ins_regex
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

    if which == "swea" or which == "gmsonco":
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
                {
                    "INFO.CSQ": {
                        "$elemMatch": {
                            "Consequence": {"$in": settings["filter_conseq"]}
                        }
                    }
                },
            ],
        }

    if which == "solid":
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
                                                "$gte": float(
                                                    settings["min_freq"]
                                                ),
                                                "$lte": float(
                                                    settings["max_freq"]
                                                ),
                                            },
                                            "DP": {
                                                "$gte": float(
                                                    settings["min_depth"]
                                                )
                                            },
                                            "VD": {
                                                "$gte": float(
                                                    settings["min_alt_reads"]
                                                )
                                            },
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
                                                        "$lte": float(
                                                            settings[
                                                                "max_control_freq"
                                                            ]
                                                        )
                                                    },
                                                    "DP": {
                                                        "$gte": float(
                                                            settings[
                                                                "min_depth"
                                                            ]
                                                        )
                                                    },
                                                }
                                            }
                                        },
                                        {
                                            "GT": {
                                                "$not": {
                                                    "$elemMatch": {
                                                        "type": "control"
                                                    }
                                                }
                                            }
                                        },
                                    ]
                                },
                                # Filters if gnomad population frequency are above the max_popfreq
                                {
                                    "$or": [
                                        {
                                            "gnomad_frequency": {
                                                "$exists": True,
                                                "$type": "number",
                                                "$lte": float(
                                                    settings["max_popfreq"]
                                                ),
                                            }
                                        },
                                        {
                                            "gnomad_frequency": {
                                                "$type": "string"
                                            }
                                        },
                                        {"gnomad_frequency": None},
                                        {
                                            "gnomad_frequency": {
                                                "$exists": False
                                            }
                                        },
                                    ]
                                },
                                # Either variant fullfills Consequence-filter or is a promoter variant in TERT.
                                {
                                    "$or": [
                                        {
                                            "INFO.selected_CSQ.Consequence": {
                                                "$in": settings[
                                                    "filter_conseq"
                                                ]
                                            }
                                        },
                                        {
                                            "INFO.CSQ": {
                                                "$elemMatch": {
                                                    "Consequence": {
                                                        "$in": settings[
                                                            "filter_conseq"
                                                        ]
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


## TERT NFKBIE


def build_pos_genes_filter(settings):
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
