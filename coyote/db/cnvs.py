from bson.objectid import ObjectId
from coyote.db.base import BaseHandler
from flask import current_app as app


class CNVsHandler(BaseHandler):
    """
    CNVs handler from coyote["cnvs"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.cnvs_collection)

    def get_sample_cnvs(self, sample_id: str, normal: bool = False, settings: dict | None = None):
        # TODO CHECK WHAT IS NORMAL IN THE PREVIOUS COYOTE
        """
        Get CNVs for a sample
        """

        query = {"SAMPLE_ID": sample_id}

        if settings:
            query = {
                "SAMPLE_ID": sample_id,
                "$and": [
                    # Ratio Condition: (cnv.ratio|float < -0.3 or cnv.ratio|float > 0.3)
                    {
                        "$or": [
                            {"ratio": {"$lte": settings["cnv_loss_cutoff"]}},
                            {"ratio": {"$gte": settings["cnv_gain_cutoff"]}},
                        ]
                    },
                    # Size and Ratio Condition:
                    {
                        "$or": [
                            {
                                "$and": [
                                    {"size": {"$gte": settings["min_cnv_size"]}},
                                    {"size": {"$lte": settings["max_cnv_size"]}},
                                ]
                            },
                            {"ratio": {"$gt": 3}},
                        ]
                    },
                    # Gene Panel Condition:
                    {
                        "$or": [
                            {"panel_gene": {"$in": settings.get("filter_genes", [])}},
                            {
                                "panel_gene": {"$exists": False}
                            },  # Handle empty dispgenes with $exists
                            {"assay": "tumwgs"},
                        ]
                    },
                ],
            }

        return self.get_collection().find(query)

    def get_cnv(self, cnv_id: str):
        """
        Get CNV by ID
        """
        return self.get_collection().find_one({"_id": ObjectId(cnv_id)})

    def get_interesting_sample_cnvs(self, sample_id: str, interesting: bool = True):
        """
        Get CNVs for a sample
        """
        return self.get_collection().find({"SAMPLE_ID": sample_id, "interesting": interesting})

    def get_cnv_annotations(self, cnv: str) -> list:
        """
        Get annotations for a CNV
        """
        var = f'{str(cnv["chr"])}:{str(cnv["start"])}-{str(cnv["end"])}'
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

    def noteworthy_cnv(self, cnv_id: str, noteworthy: bool = True) -> None:
        """
        Mark CNV as Note worthy
        """
        self.mark_noteworthy(cnv_id, noteworthy)

    def unnoteworthy_cnv(self, cnv_id: str, noteworthy: bool = False) -> None:
        """
        UnMark CNV as Note worthy
        """
        self.mark_noteworthy(cnv_id, noteworthy)

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

    def add_cnv_comment(self, cnv_id: str, comment_doc: dict) -> None:
        """
        Add comment to a CNV
        """
        self.update_comment(cnv_id, comment_doc)

    def hidden_cnv_comments(self, id: str) -> bool:
        """
        Return True if hidden cnv comments else False
        """
        return self.hidden_comments(id)

    def get_unique_cnv_count(self) -> int:
        """
        Get unique CNVs
        """
        query = [
            {"$group": {"_id": {"chr": "$chr", "start": "$start", "end": "$end"}}},
            {"$group": {"_id": None, "uniqueCnvCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueCnvCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    def delete_sample_cnvs(self, sample_oid: str) -> None:
        """
        Delete CNVs for a sample
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
