from coyote.db.base import BaseHandler
from flask import current_app as app
from functools import lru_cache


class PanelsHandler(BaseHandler):
    """
    Coyote gene panels db actions
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.panels_collection)

    def get_assay_panels(self, assay: str) -> list:
        panels = list(self.get_collection().find({"assays": {"$in": [assay]}}))
        gene_lists = {}
        for panel in panels:
            if panel["type"] == "genelist":
                gene_lists[panel["name"]] = panel["genes"]
        return gene_lists, panels

    def get_panel(self, type: str, subpanel: str):
        panel = self.get_collection().find_one({"name": subpanel, "type": type})
        return panel

    @lru_cache(maxsize=2)
    def get_unique_all_panel_gene_count(self) -> int:
        """
        Get unique gene count from all the panels
        """
        query = [
            # {"$match": {"type": "genelist"}},
            {"$unwind": "$genes"},
            {"$group": {"_id": "$genes"}},
            {"$group": {"_id": None, "uniqueGenesCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueGenesCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    @lru_cache(maxsize=2)
    def get_assay_gene_counts(self):
        """
        Get a dictionary where assays are keys and counts of genes are values
        """
        query = [
            {"$unwind": "$assays"},
            {"$unwind": "$genes"},
            {"$group": {"_id": {"assay": "$assays", "gene": "$genes"}}},
            {"$group": {"_id": "$_id.assay", "uniqueGeneCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            assay_gene_counts = {doc["_id"]: doc["uniqueGeneCount"] for doc in result}
            return assay_gene_counts
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return {}

    @lru_cache(maxsize=2)
    def get_genelist_gene_counts(self):
        """
        Get a dictionary where display names (gene list names) are keys and counts of genes are values
        """
        query = [
            {"$unwind": "$genes"},
            {"$group": {"_id": {"displayname": "$displayname", "gene": "$genes"}}},
            {"$group": {"_id": "$_id.displayname", "uniqueGeneCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            genelist_gene_counts = {doc["_id"]: doc["uniqueGeneCount"] for doc in result}
            return genelist_gene_counts
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return {}
