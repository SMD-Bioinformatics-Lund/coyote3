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

from flask import current_app as app
import re


def build_query(sample_settings, group) -> dict:
    """
    build a default query, or add group configured queries.
    """
    query = {}
    query["SAMPLE_ID"] = sample_settings["id"]
    group_query = group.get("query")
    ## Global OR-statement, will override everything else
    globalor = []

    # Show GERMLINE for paired or not, and with the option to override pipeline settings for genes. Default query NO germline
    ## check in config if germline should be forced to view
    if group_query != None and "GERMLINE" in group_query:
        ## get override germline genes from config
        germ = []
        germ.append({"FILTER": {"$in": ["GERMLINE"]}})
        genes = ["ABC", "DEF"]
        germline_genes = []
        for gene in genes:
            germline_genes.append(
                {"INFO.CSQ": {"$elemMatch": {"SYMBOL": {gene}}}}
            )
        if germline_genes:
            germ.append({"$or": germline_genes})
        globalor.append(germ)

    ### AND STATEMENTS ###
    # one part of global OR that can be fulfilled, all categories within AND needs to be fulfilled
    form_list = []

    ## CASE ## UNMUTABLE!
    case_keys = {}
    case_keys["type"] = "case"
    case_keys["AF"] = {"$gte": float(sample_settings["min_freq"])}
    case_keys["DP"] = {"$gte": float(sample_settings["min_depth"])}
    case_keys["VD"] = {"$gte": float(sample_settings["min_reads"])}
    form_list.append({"GT": {"$elemMatch": case_keys}})

    ## CONTROL ## UNMUTABLE!
    control_keys = {}
    control_keys["type"] = "control"
    control_keys["AF"] = {"$lte": float(sample_settings["max_freq"])}
    control_keys["DP"] = {"$gte": float(sample_settings["min_depth"])}
    # if control exist, match filters, OR if no control fulfill the control AND statement
    form_list.append(
        {
            "$or": [
                {"GT": {"$elemMatch": control_keys}},
                {"$not": {"GT": {"$elemMatch": {"type": "control"}}}},
            ]
        }
    )
    ## VEP CSQ ##
    default_csq = {
        "INFO.CSQ": {
            "$elemMatch": {
                "Consequence": {"$in": sample_settings["filter_conseq"]}
            }
        }
    }
    # Any configured thing that should overwrite VEP-CSQ
    test = 1
    test2 = 0
    csq_or = [default_csq]

    # check different configs
    if test:
        csq_or.append(FLT_LARGE_INS())
    if test2:
        csq_or.append(FLT_LARGE_INS())

    # if any configs were added make it an OR, else just add consequence
    if len(csq_or) > 1:
        form_list.append({"$and": csq_or})
    else:
        form_list.append(default_csq)

    ## ADD ALL AND-statements to GLOBAL OR
    globalor.append({"$and": form_list})

    ## ADD the global OR to the query, or just use default AND-statement
    if no_or_statements > 0:
        query["$or"] = globalor
    else:
        query['$and'] = form_list

    return query


def FLT_LARGE_INS():

    large_ins_regex = re.compile(r"\w{10,200}", re.IGNORECASE)
    flt3 = {
        "$and": [
            {"INFO.CSQ": {"$elemMatch": {"SYMBOL": "FLT3"}}},
            {
                "$or": [
                    {"INFO.SVTYPE": {"$exists": "true"}},
                    {"ALT": large_ins_regex},
                ]
            },
        ]
    }
    return large_ins

def REGULATORY_VARIANTS():
    """
    define if some promoter variants should show for specific genes

    1 gene: '$and' : { genesymbol : gene}, { csq: TF_BINDING, REGULATORY }
    2 or more genes: '$and' : {'$or' : { genesymbol:gene1}, { genesymbol:gene2}, { genesymbol:gene3} }, { csq: TF_BINDING, REGULATORY }
    """
    