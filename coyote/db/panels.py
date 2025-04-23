from coyote.db.base import BaseHandler
from flask import current_app as app
from functools import lru_cache
from bson.objectid import ObjectId
from datetime import datetime
from flask_login import current_user


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

    @lru_cache(maxsize=2)
    def get_assay_panel_names(self, assay: str) -> dict:
        """
        Get panel name, display name and panel type for a given assay
        """

        return list(
            self.get_collection().find(
                {"assays": {"$in": [assay]}}, {"name": 1, "displayname": 1, "type": 1}
            )
        )

    def get_panel(self, type: str, subpanel: str):
        panel = self.get_collection().find_one({"name": subpanel, "type": type})
        return panel

    def panel_exists(self, type: str, subpanel: str) -> bool:
        """
        Check if a panel of given type and subpanel name exists in the collection.
        """
        return self.get_collection().count_documents({"name": subpanel, "type": type}, limit=1) > 0

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

    def get_all_panel_assays(self):
        """
        Get all panel assays
        """
        query = [
            {"$unwind": "$assays"},
            {"$group": {"_id": "$assays"}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            assays = [doc["_id"] for doc in result]
            return assays
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return []

    def get_assay_all_panels(self, assay):
        query = [
            {"$match": {"assays": {"$in": [assay]}}},
            {
                "$project": {
                    "type": 1,
                    "name": 1,
                    "displayname": 1,
                    "assays": 1,
                    "last_updated": {"$arrayElemAt": ["$changelog", -1]},
                    "genes": 1,
                    "_id": 1,
                }
            },
        ]

        panels = list(self.get_collection().aggregate(query))
        return panels

    def get_panel_genes(self, gene_panel_id):
        """
        Get the genes in a gene panel
        """
        gene_panel = self.get_collection().find_one({"_id": ObjectId(gene_panel_id)})
        return gene_panel.get("genes", [])

    def get_genepanel(self, genepanel_id):
        """
        Get a gene panel
        """
        return self.get_collection().find_one({"_id": ObjectId(genepanel_id)})

    def validate_panel_field(self, field_name, value, genepanel_id=None):
        # Query to find a panel with the specified field value
        query = {field_name: value}

        if genepanel_id:
            # If a genepanel_id is provided, exclude the panel with this ID from the search
            query["_id"] = {"$ne": ObjectId(genepanel_id)}

        # Find a panel that matches the query
        existing_panel = self.get_collection().find_one(query, {"_id": 1})
        # Return True if a panel is not found, meaning the name/displayname is not in use by another panel
        return existing_panel is None

    def update_genelist(self, data: dict):
        """
        Insert a gene panel
        """
        name = data.get("name")
        displayname = data.get("displayname")
        type_ = data.get("type")
        assays = data.get("assays").split(",")
        changelog = data.get("changelog", [])
        changelog.append(
            {
                "change": "created" if not data.get("changelog") else "updated",
                "version": data.get("version"),
                "timestamp": datetime.now(),
                "user": current_user.username,
            }
        )

        # Handle file upload or text input
        genes = []
        if data.get("genes_file"):
            genes_file = data.get("genes_file").read().decode("utf-8").splitlines()
            genes = [gene.strip() for gene in genes_file if gene.strip()]
        elif data.get("genes_text"):
            genes = [gene.strip() for gene in data.get("genes_text").split(",") if gene.strip()]

        # creating a document
        new_genelist = {
            "name": name,
            "displayname": displayname,
            "type": type_,
            "genes": list(set(genes)),
            "assays": list(set(assays)),
            "changelog": changelog,
        }

        if data.get("_id"):
            return self.get_collection().update_one(
                {"_id": ObjectId(data.get("_id"))}, {"$set": new_genelist}
            )
        else:
            return self.get_collection().insert_one(new_genelist)

    def delete_genelist(self, genelist_id):
        """
        Delete a gene panel
        """
        return self.get_collection().delete_one({"_id": ObjectId(genelist_id)})

    def get_latest_genepanel_version(self, genepanel_id):
        """
        Get the latest version of a panel
        """
        query = [
            {"$match": {"_id": ObjectId(genepanel_id)}},
            {"$unwind": "$changelog"},
            {"$sort": {"changelog.timestamp": -1}},
            {"$group": {"_id": "$_id", "latestVersion": {"$first": "$changelog.version"}}},
        ]
        return list(self.get_collection().aggregate(query))[0].get("latestVersion", 0)

    def get_assay_gene_panel_genes(self, assay: str):
        """
        Get all the genes for the assay panel itself
        """
        assay_gene_lists = self.get_collection().find({"assays": {"$in": [assay]}, "default": True})
        return assay_gene_lists

    def get_assay_gene_list_by_name(self, assay: str, names_list: list):
        """
        Get gene list for assay by name
        """
        if not names_list:
            return None

        assay_gene_lists = self.get_collection().find(
            {"assays": {"$in": [assay]}, "name": {"$in": names_list}}
        )
        return assay_gene_lists
