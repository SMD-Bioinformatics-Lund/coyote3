from bson.objectid import ObjectId
from coyote.db.base import BaseHandler


class TranslocsHandler(BaseHandler):

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.transloc_collection)

    def get_sample_translocations(self, sample_id: str):
        return self.get_collection().find({"SAMPLE_ID": sample_id})

    def get_transloc(self, transloc_id: str) -> dict:
        """
        Get Tranlocation by ID
        """
        return self.get_collection().find_one({"_id": ObjectId(transloc_id)})

    def get_transloc_annotations(self, tl: dict) -> dict:
        var = f'{str(tl["CHROM"])}:{str(tl["POS"])}^{tl["ALT"]}'
        annotations = self.adapter.annotations_collection.find({"variant": var}).sort(
            "time_created", 1
        )

        # latest_classification = {'class':999}
        annotations_arr = []
        for anno in annotations:
            if "class" in anno:
                latest_classification = anno
            elif "text" in anno:
                annotations_arr.append(anno)

        return annotations_arr  # , latest_classification

    def mark_interesting_transloc(self, transloc_id: str, interesting: bool = True) -> None:
        """
        Mark Translocations as interesting
        """
        self.mark_interesting(transloc_id, interesting)

    def unmark_interesting_transloc(self, transloc_id: str, interesting: bool = False) -> None:
        """
        Unmark Translocations as interesting
        """
        self.mark_interesting(transloc_id, interesting)

    def mark_false_positive_transloc(self, transloc_id: str, fp: bool = True) -> None:
        """
        Mark / Unmark Translocations as false
        """
        self.mark_false_positive(transloc_id, fp)

    def unmark_false_positive_transloc(self, transloc_id: str, fp: bool = False) -> None:
        """
        Mark / Unmark Translocations as false
        """
        self.mark_false_positive(transloc_id, fp)

    def hide_transloc_comment(self, transloc_id: str, comment_id: str) -> None:
        """
        Hide / Unhide Translocation comment
        """
        self.hide_comment(transloc_id, comment_id)

    def unhide_transloc_comment(self, transloc_id: str, comment_id: str) -> None:
        """
        Unhide Translocation comment
        """
        self.unhide_comment(transloc_id, comment_id)

    def add_transloc_comment(self, transloc_id: str, comment: str) -> None:
        """
        Add comment to a Translocation
        """
        self.update_comment(transloc_id, comment)
