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

    def cnvtype_variant(self, cnvs: list, checked_effects: list) -> list:
        """
        Filter CNVs by type
        """
        filtered_cnvs = []
        for var in cnvs:
            if var["ratio"] > 0:
                effect = "AMP"
            if var["ratio"] < 0:
                effect = "DEL"
            if effect in checked_effects:
                filtered_cnvs.append(var)
        return filtered_cnvs

    def cnv_organizegenes(self, cnvs: list) -> list:
        """
        Organize CNV genes
        """
        fixed_cnvs_genes = []
        for var in cnvs:
            var["other_genes"] = []
            for gene in var["genes"]:
                if "class" in gene:
                    if "panel_gene" in var:
                        var["panel_gene"].append(gene["gene"])
                    else:
                        var["panel_gene"] = [gene["gene"]]
                else:
                    var["other_genes"].append(gene["gene"])
            fixed_cnvs_genes.append(var)
        return fixed_cnvs_genes

    def hidden_cnv_comments(self, id: str) -> bool:
        """
        Return True if hidden cnv comments else False
        """
        return self.hidden_comments(id)

