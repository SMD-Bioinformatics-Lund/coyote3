from coyote.db.base import BaseHandler
from datetime import datetime


class AssayConfigsHandler(BaseHandler):
    """
    Assay Configs handler from coyote["assay_configs"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.assay_configs_collection)

    def get_assay_names(self) -> dict:
        """
        Get all the available assay names data
        """

        assays = self.get_collection().find({}, {"assay_name": 1})
        return [a["assay_name"] for a in assays]

    def get_assay_config(self, name: str) -> dict:
        return self.get_collection().find_one({"assay_name": name}, {"_id": 0})

    def replace_config(self, name: str, data: dict, updated_by: str = "admin"):
        existing = self.get_collection().find_one({"assay_name": name}) or {}
        data["created"] = existing.get("created", datetime.utcnow())
        data["created_by"] = existing.get("created_by", updated_by)

        data["updated"] = datetime.utcnow()
        data["updated_by"] = updated_by
        data["assay_name"] = name
        self.get_collection().replace_one({"assay_name": name}, data, upsert=True)
