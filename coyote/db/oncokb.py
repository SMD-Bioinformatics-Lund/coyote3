import pymongo
from bson.objectid import ObjectId
from flask import current_app as app


class OnkoKBHandler:
    def get_oncokb_anno(self, variant: dict, oncokb_hgvsp: str) -> dict:
        return self.oncokb_collection.find_one(
            {"Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"], "Alteration": {"$in": oncokb_hgvsp}}
        )

    def get_oncokb_action(self, variant: dict, oncokb_hgvsp: str) -> dict:
        return self.oncokb_actionable_collection.find(
            {
                "Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                "Alteration": {"$in": [oncokb_hgvsp, "Oncogenic Mutations"]},
            }
        )

    def get_oncokb_gene(self, gene: str) -> dict:
        return self.oncokb_genes_collection.find_one({"name": gene})
