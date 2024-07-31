import pymongo
from bson.objectid import ObjectId
from datetime import datetime
from coyote.db.base import BaseHandler


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
        return None  # type: ignore

    def get_fusion_annotations(self, fusion: list) -> tuple:
        """
        Return annotations and the latest classification for a given fusion.
        """

        selected_call = self.get_selected_fusioncall(fusion)
        if selected_call and "breakpoint1" in selected_call and "breakpoint2" in selected_call:
            variant = f"{selected_call['breakpoint1']}^{selected_call['breakpoint2']}"
            annotations_cursor = self.adapter.annotations_collection.find(
                {"variant": variant}
            ).sort("time_created", 1)
        else:
            annotations_cursor = []

        latest_classification = {"class": 999}
        annotations_list = []

        for annotation in annotations_cursor:
            if "class" in annotation:
                latest_classification = annotation
            elif "text" in annotation:
                annotations_list.append(annotation)
        return annotations_list, latest_classification

    def get_fusion(self, id: str) -> dict:
        """
        Return variant with variant ID
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    def mark_false_positive_fusion(self, fusion_id: str, fp: bool = True) -> None:
        """
        Mark fusion false positive status
        """
        self.mark_false_positive(fusion_id, fp)

    def unmark_false_positive_fusion(self, fusion_id: str, fp: bool = False) -> None:
        """
        Unmark variant false positive status
        """
        self.mark_false_positive(fusion_id, fp)

    def pick_fusion(self, id, callidx, num_calls):

        for i in range(int(num_calls)):
            self.get_collection().update(
                {"_id": ObjectId(id)}, {"$set": {"calls." + str(i) + ".selected": 0}}
            )

        self.get_collection().update(
            {"_id": ObjectId(id)}, {"$set": {"calls." + str(int(callidx) - 1) + ".selected": 1}}
        )

    def hide_fus_comment(self, id: str, comment_id: str) -> None:
        """
        Hide variant comment
        """
        self.hide_comment(id, comment_id)

    def unhide_fus_comment(self, id: str, comment_id: str) -> None:
        """
        Unhide variant comment
        """
        self.unhide_comment(id, comment_id)

    def add_fusion_comment(self, id: str, comment: dict) -> None:
        """
        Add variant comment
        """
        self.update_comment(id, comment)
