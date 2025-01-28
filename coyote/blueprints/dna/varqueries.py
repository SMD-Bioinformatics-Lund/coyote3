import re


def build_query(which, settings):

    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    gene_pos_filter = build_pos_genes_filter(settings)

    # Myeloid requires settings: min_freq, min_depth, min_reads, max_freq, filter_conseq(list)

    if which == "myeloid" or which == "fusion" or which == "tumwgs" or which == "unknown":
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
            ],  # gene_pos_filter
            "$or": [
                {"INFO.MYELOID_GERMLINE": 1},
                {"FILTER": {"$in": ["GERMLINE"]}, "INFO.CSQ": {"$elemMatch": {"SYMBOL": "CEBPA"}}},
                {"$and": [{"POS": {"$gt": 115256520}}, {"POS": {"$lt": 115256538}}, {"CHROM": 1}]},
                {
                    "$and": [
                        # Case sample fulfills filter critieria
                        {
                            "GT": {
                                "$elemMatch": {
                                    "type": "case",
                                    "AF": {"$gte": float(settings["min_freq"])},
                                    "DP": {"$gte": float(settings["min_depth"])},
                                    "VD": {"$gte": float(settings["min_reads"])},
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
                                            "AF": {"$lte": float(settings["max_freq"])},
                                            "DP": {"$gte": float(settings["min_depth"])},
                                        }
                                    }
                                },
                                {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
                            ]
                        },
                        # Either variant fullfills Consequence-filter or is a structural variant in FLT3.
                        {
                            "$or": [
                                {
                                    "INFO.CSQ": {
                                        "$elemMatch": {
                                            "Consequence": {"$in": settings["filter_conseq"]}
                                        }
                                    }
                                },
                                {
                                    "$and": [
                                        {"INFO.CSQ": {"$elemMatch": {"SYMBOL": "FLT3"}}},
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
                            "AF": {"$gte": float(settings["min_freq"])},
                            "DP": {"$gte": float(settings["min_depth"])},
                            "VD": {"$gte": float(settings["min_reads"])},
                        }
                    }
                },
                # Either variant fullfills Consequence-filter or is a structural variant in FLT3.
                {"INFO.CSQ": {"$elemMatch": {"Consequence": {"$in": settings["filter_conseq"]}}}},
            ],
        }

    if which == "solid":
        query = {
            "SAMPLE_ID": settings["id"],
            "$and": [
                gene_pos_filter,
            ],  # gene_pos_filter
            "$or": [
                {"FILTER": {"$in": ["GERMLINE"]}},
                {
                    "$and": [
                        # Case sample fulfills filter critieria
                        {
                            "GT": {
                                "$elemMatch": {
                                    "type": "case",
                                    "AF": {"$gte": float(settings["min_freq"])},
                                    "DP": {"$gte": float(settings["min_depth"])},
                                    "VD": {"$gte": float(settings["min_reads"])},
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
                                            "AF": {"$lte": float(settings["max_freq"])},
                                            "DP": {"$gte": float(settings["min_depth"])},
                                        }
                                    }
                                },
                                {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
                            ]
                        },
                        # Either variant fullfills Consequence-filter or is a promoter variant in TERT.
                        {
                            "$or": [
                                {
                                    "INFO.CSQ": {
                                        "$elemMatch": {
                                            "Consequence": {"$in": settings["filter_conseq"]}
                                        }
                                    }
                                },
                                {
                                    "$and": [
                                        {
                                            "$or": [
                                                {"INFO.CSQ": {"$elemMatch": {"SYMBOL": "TERT"}}},
                                                {"INFO.CSQ": {"$elemMatch": {"SYMBOL": "NFKBIE"}}},
                                            ]
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
            ],
        }
    return query


## TERT NFKBIE


def build_pos_genes_filter(settings):
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])

    if pos_list:
        return {"POS": {"$in": pos_list}}
    elif genes_list:
        return {"genes": {"$in": genes_list}}
    else:
        return {}
