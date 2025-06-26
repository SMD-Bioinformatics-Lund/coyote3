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

from functools import lru_cache
from datetime import datetime
from collections import defaultdict, OrderedDict
from typing import Dict, Tuple, List, Generator, Any
from coyote.util.common_utility import CommonUtility


class DashBoardUtility:
    """
    Utility class for Dashboard blueprint
    """

    @staticmethod
    def convert_annotations_to_hashable(annotations):
        # Helper function to convert datetime to string
        def datetime_to_hashable(dt):
            return dt.isoformat()

        converted = []
        for annotation in annotations:
            annotation["time_created"] = datetime_to_hashable(
                annotation["time_created"]
            )
            converted.append(frozenset(annotation.items()))
        return tuple(converted)

    @staticmethod
    def format_classified_stats(class_stats_dict: dict) -> dict:
        """
        Format classified stats
        """
        class_stats = OrderedDict()

        for doc in class_stats_dict:
            if doc["_id"].get("assay") is not None:
                continue
            else:
                nomenclature = doc["_id"]["nomenclature"]
                if nomenclature == "f":
                    nomenclature = "fusion"
                elif nomenclature == "g":
                    nomenclature = "genomic"
                elif nomenclature == "c":
                    nomenclature = "cnv"
                elif nomenclature == "p":
                    nomenclature = "protein"
                else:
                    nomenclature = "no_nomenclature"
                class_value = doc["_id"]["class"]
                count = doc["count"]
                if nomenclature not in class_stats:
                    class_stats[nomenclature] = OrderedDict()
                class_stats[nomenclature][class_value] = count

        return class_stats

    @staticmethod
    def format_assay_classified_stats(class_stats_dict: dict) -> dict:
        """
        Format classified stats
        """
        assay_class_stats = OrderedDict()

        for doc in class_stats_dict:
            assay = doc["_id"].get("assay", "NA")
            if assay == "NA":
                continue
            else:
                nomenclature = doc["_id"]["nomenclature"]
                class_value = doc["_id"]["class"]
                count = doc["count"]

                if assay not in assay_class_stats:
                    assay_class_stats[assay] = OrderedDict()

                if nomenclature not in assay_class_stats[assay]:
                    assay_class_stats[assay][nomenclature] = OrderedDict()

                assay_class_stats[assay][nomenclature][class_value] = count

        if None in assay_class_stats:
            assay_class_stats["no_assay"] = assay_class_stats.pop(None)
        return assay_class_stats

    @staticmethod
    def format_asp_gene_stats(data: dict) -> dict:
        """
        Format ASP gene stats
        """
        result = {}
        for doc in data:
            doc_dict = dict(doc)
            key = doc_dict.pop("_id", None)
            if key is not None:
                result[key] = doc_dict

        grouped = defaultdict(list)
        for assay_id, details in result.items():
            group = details.get("asp_group", "Unknown")
            grouped[group].append(details)
        return grouped
