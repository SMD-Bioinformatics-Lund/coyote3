from coyote.db.base import BaseHandler
from datetime import datetime
from bson.objectid import ObjectId


class AssayConfigsHandler(BaseHandler):
    """
    Assay Configs handler from coyote["assay_configs"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.assay_configs_collection)

    def get_all_assay_configs(self) -> list:
        """
        Get all the assay configs
        """
        return self.get_collection().find({})

    def get_assay_names(self) -> dict:
        """
        Get all the available assay names data
        """
        assays = self.get_collection().find({}, {"assay_name": 1})
        return [a["assay_name"] for a in assays]

    def get_assay_config(self, assay_id: str) -> dict:
        return self.get_collection().find_one({"_id": assay_id})

    def replace_config(self, name: str, data: dict, updated_by: str = "admin"):
        existing = self.get_collection().find_one({"assay_name": name}) or {}
        data["created"] = existing.get("created", datetime.utcnow())
        data["created_by"] = existing.get("created_by", updated_by)

        data["updated"] = datetime.utcnow()
        data["updated_by"] = updated_by
        data["assay_name"] = name
        self.get_collection().replace_one({"assay_name": name}, data, upsert=True)

    def update_assay_config(self, assay_name: str, data: dict):
        """
        Update the assay config
        """
        return self.get_collection().update_one({"assay_name": assay_name}, {"$set": data})

    def insert_assay_config(self, data: dict):
        """
        Insert a new assay config
        """
        return self.get_collection().insert_one(data)
