import pymongo
from bson.objectid import ObjectId
from datetime import datetime
from coyote.db.base import BaseHandler
from flask import current_app as app


class FusionsHandler(BaseHandler):
    """
    Fusions handles for fusions collections from the database
    for ex: coyote["fusions"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.fusions_collection)

    def get_sample_fusions(self, query: dict) -> dict:
        """
        Return fusions with according to a constructed varquery
        """
        return self.adapter.fusions_collection.find(query)

    def get_selected_fusioncall(self, fusion: list) -> dict:
        """
        Return the selected fusion call from the fusion data
        """
        for call in fusion.get("calls", []):
            if call.get("selected") == 1:
                return call
        return None

    def get_fusion_annotations(self, fusion: list) -> dict:
        """
        Return annotations and latest classification for a given fusion
        """
        call = self.get_selected_fusioncall(fusion)
        if call and "breakpoint1" in call and "breakpoint2" in call:
            annotations = self.adapter.annotations_collection.find(
                {"variant": f"{call['breakpoint1']}^{call['breakpoint2']}"}
            ).sort("time_created", 1)
        else:
            annotations = None

        latest_classification = {"class": 999}
        annotations_arr = []
        if annotations:
            for anno in annotations:
                if "class" in anno:
                    latest_classification = anno
                elif "text" in anno:
                    annotations_arr.append(anno)

        return (annotations_arr, latest_classification)

    def get_fusion(self, id: str) -> dict:
        """
        Return variant with variant ID
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    def get_unique_fusion_count(self) -> int:
        """
        Get unique Fusions
        """
        query = [
            {"$group": {"_id": {"genes": "$genes"}}},
            {"$group": {"_id": None, "uniqueFusionCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueFusionCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0
