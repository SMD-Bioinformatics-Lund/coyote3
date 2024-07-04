from bson.objectid import ObjectId
from coyote.db.base import BaseHandler

class CNVsHandler(BaseHandler):
    """
    CNVs handler from coyote["cnvs"]
    """
    

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.cnvs_collection)

    def get_sample_cnvs(self, sample_id: str, normal: bool = False):
        """
        Get CNVs for a sample
        """
        return self.get_collection().find({"SAMPLE_ID": sample_id})

    def get_cnv(self, cnv_id: str):
        """
        Get CNV by ID
        """
        return self.get_collection().find_one({"_id": ObjectId(cnv_id)})

    def get_cnv_annotations(self, cnv: str) -> list:
        """
        Get annotations for a CNV
        """
        var = f"{str(cnv["chr"])}:{str(cnv["start"])}-{str(cnv["end"])}"
        annotations = self.adapter.annotations_collection.find(
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

    def mark_interesting_cnv(self, cnv_id: str, interesting: bool = True) -> None:
        """
        Mark CNV as interesting 
        """
        self.mark_interesting(cnv_id, interesting)

    def unmark_interesting_cnv(self, cnv_id: str, interesting: bool = False) -> None:
        """
        Unmark CNV as interesting 
        """
        self.mark_interesting(cnv_id, interesting)

    def mark_false_positive_cnv(self, cnv_id: str, fp: bool = True) -> None:
        """
        Mark CNV as false positive
        """
        self.mark_false_positive(cnv_id, fp)

    def unmark_false_positive_cnv(self, cnv_id: str, fp: bool = False) -> None:
        """
        UnMark CNV as false positive
        """
        self.mark_false_positive(cnv_id, fp)

    def hide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Hide CNVs comment
        """
        self.hide_comment(cnv_id, comment_id)

    def unhide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Unhide CNVs comment
        """
        self.unhide_comment(cnv_id, comment_id)