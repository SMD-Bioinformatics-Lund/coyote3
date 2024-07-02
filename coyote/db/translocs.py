from bson.objectid import ObjectId
from flask_login import current_user
from datetime import datetime
from pymongo.collection import Collection


class TranslocsHandler:

    def get_sample_translocations(self, sample_id: str):
        transloc_iter = self.transloc_collection.find({"SAMPLE_ID": sample_id})
        return transloc_iter

    def get_transloc(self, transloc_id: str) -> dict:
        """
        Get Tranlocation by ID
        """
        transloc = self.transloc_collection.find_one({"_id": ObjectId(transloc_id)})
        return transloc

    def get_transloc_annotations(self, tl: dict) -> dict:
        var = f'{str(tl["CHROM"])}:{str(tl["POS"])}^{tl["ALT"]}'

        annotations = self.annotations_collection.find({"variant": var}).sort("time_created", 1)

        # latest_classification = {'class':999}
        annotations_arr = []
        for anno in annotations:
            if "class" in anno:
                latest_classification = anno
            elif "text" in anno:
                annotations_arr.append(anno)

        return annotations_arr  # , latest_classification

    def is_intresting_transloc(self, transloc_id: str, intresting: bool) -> None:
        """
        Mark/Unmark Translocations as interesting
        """
        self.transloc_collection.update_one(
            {"_id": ObjectId(transloc_id)},
            {"$set": {"interesting": intresting}},
        )
        return None

    def mark_false_positive_transloc(self, transloc_id: str, fp: bool) -> None:
        """
        Mark / Unmark Translocations as false
        """
        self.transloc_collection.update_one(
            {"_id": ObjectId(transloc_id)},
            {"$set": {"fp": fp}},
        )
        return None

    def hide_transloc_comment(
        self, transloc_id: str, comment_id: str, collection: Collection
    ) -> None:
        """
        Hide / Unhide Translocation comment
        """
        collection.update_one(
            {"_id": ObjectId(transloc_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 1,
                    "comments.$.hidden_by": current_user.get_id(),
                    "comments.$.time_hidden": datetime.now(),
                }
            },
        )

    def unhide_transloc_comment(
        self, transloc_id: str, comment_id: str, collection: Collection
    ) -> None:
        """
        Unhide Translocation comment
        """
        collection.update_one(
            {"_id": ObjectId(transloc_id), "comments._id": ObjectId(comment_id)},
            {"$set": {"comments.$.hidden": 0}},
        )
