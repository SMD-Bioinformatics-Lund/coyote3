"""Group assay-panel gene statistics for dashboard payloads."""

from collections import defaultdict


class DashBoardUtility:
    """Utility class for dashboard-specific payload shaping."""

    @staticmethod
    def format_asp_gene_stats(data: dict) -> dict:
        """Group deduplicated ASP gene-statistic records by assay group.

        Args:
            data: Iterable of documents containing _id and optional asp_group.

        Returns:
            A defaultdict(list) of shallow-copied details without _id, grouped by
            asp_group. Missing groups use "Unknown"; explicit null groups use None.
            Null or missing IDs are skipped and the last record for each ID wins.
            Input documents are not mutated.
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
