from collections import defaultdict


class DashBoardUtility:
    """Utility class for dashboard-specific payload shaping."""

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
