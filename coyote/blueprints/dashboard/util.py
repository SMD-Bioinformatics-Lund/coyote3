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

from hashlib import md5
from collections import defaultdict, OrderedDict


class DashBoardUtility:
    """
    Utility class providing helper methods for formatting and processing dashboard-related data,
    such as classified statistics, assay statistics, ASP gene statistics, and cache key generation.
    """

    @staticmethod
    def format_classified_stats(class_stats_dict: dict) -> dict:
        """
        Formats classified statistics by converting nomenclature codes to descriptive names
        and organizing the data into an ordered dictionary grouped by nomenclature and class.

        Args:
            class_stats_dict (dict): A dictionary containing classified statistics.

        Returns:
            dict: An ordered dictionary with formatted classified statistics grouped by nomenclature and class.
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
        Formats classified statistics for assays.

        Args:
            class_stats_dict (dict): A dictionary containing classified statistics.

        Returns:
            dict: An ordered dictionary with formatted classified statistics grouped by assay and nomenclature.
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
        Formats ASP gene statistics by grouping details based on the `asp_group` field.

        Args:
            data (dict): A list of documents containing ASP gene statistics.

        Returns:
            dict: A dictionary grouping ASP gene details by their `asp_group` value.
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

    @staticmethod
    def generate_dashboard_chache_key(username: str) -> str:
        """
        Generates a cache key for dashboard data based on the provided username.

        Args:
            username (str): The username for which to generate the cache key.

        Returns:
            str: A unique cache key string for the user's dashboard data.
        """
        raw_key = f"dashboard_data_{username}"
        return f"dashboard:{md5(raw_key.encode()).hexdigest()}"
