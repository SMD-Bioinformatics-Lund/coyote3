from bson.objectid import ObjectId
from flask_login import current_user
from datetime import datetime


class CNVsHandler:

    def get_sample_cnvs(self, sample_id: str, normal: bool = False):
        """
        Get CNVs for a sample
        """
        cnv_iter = self.cnvs_collection.find({"SAMPLE_ID": sample_id})
        return cnv_iter

    def get_cnv(self, cnv_id: str):
        """
        Get CNV by ID
        """
        cnv = self.cnvs_collection.find_one({"_id": ObjectId(cnv_id)})
        return cnv

    def get_cnv_annotations(self, cnv: str) -> list:
        """
        Get annotations for a CNV
        """
        var = f"{str(cnv["chr"])}:{str(cnv["start"])}-{str(cnv["end"])}"
        annotations = self.annotations_collection.find(
            {"variant": var}
        ).sort("time_created", 1)

        # latest_classification = {'class':999}
        annotations_arr = []
        for anno in annotations:
            if "class" in anno:
                latest_classification = anno
            elif "text" in anno:
                annotations_arr.append(anno)

        return annotations_arr  # , latest_classification

    def is_intresting_cnv(self, cnv_id: str, intresting: bool) -> None:
        """
        Mark/Unmark CNV as interesting 
        """
        self.cnvs_collection.update_one(
            {"_id": ObjectId(cnv_id)},
            {"$set": {"interesting": intresting}},
        )
        return None

    def mark_false_positive_cnv(self, cnv_id: str, fp: bool) -> None:
        """
        Mark CNV as false
        """
        self.cnvs_collection.update_one(
            {"_id": ObjectId(cnv_id)},
            {"$set": {"fp": fp}},
        )
        return None

    def hide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Hide CNVs comment
        """
        self.cnvs_collection.update_one(
            {"_id": ObjectId(cnv_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 1,
                    "comments.$.hidden_by": current_user.get_id(),
                    "comments.$.time_hidden": datetime.now(),
                }
            },
        )
        return None

    def unhide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Unhide CNVs comment
        """
        self.cnvs_collection.update_one(
            {"_id": ObjectId(cnv_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 0,
                }
            },
        )
        return None