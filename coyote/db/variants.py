from bson.objectid import ObjectId
import re
from coyote.db.base import BaseHandler
from flask import current_app as app


class VariantsHandler(BaseHandler):
    """
    Variants handler from coyote["variants_idref"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.variants_collection)

    def get_sample_ids(self, sample_id: str):
        a_var = self.get_collection().find_one({"SAMPLE_ID": sample_id}, {"GT": 1})
        ids = {}
        if a_var:
            for gt in a_var["GT"]:
                ids[gt.get("type")] = gt.get("sample")
        return ids

    def get_num_samples(self, sample_id: str) -> int:
        """
        Get number of samples
        """
        gt = self.get_collection().find_one({"SAMPLE_ID": sample_id}, {"GT": 1})
        if gt:
            return len(gt.get("GT"))
        else:
            return 0

    def get_case_variants(self, query: dict):
        """
        Return variants with according to a constructed varquery
        """
        return self.get_collection().find(query)

    def get_variant(self, id: str) -> dict:
        """
        Return variant with variant ID
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    def get_variant_in_other_samples(self, variant, assay=None) -> dict:
        """
        Return same variant from other samples of a specific assay
        """
        query = {
            "simple_id": variant["simple_id"],
            "SAMPLE_ID": {"$ne": variant["SAMPLE_ID"]},
        }

        other_variants = self.get_collection().find(query).limit(20)

        sample_names = self.adapter.samples_collection.find({}, {"_id": 1, "name": 1, "groups": 1})
        name = {}
        for samp in sample_names:
            name[str(samp["_id"])] = samp["name"]

        other = []
        for var in other_variants:
            var["sample_name"] = name.get(var["SAMPLE_ID"], "unknown")
            other.append(var.copy())

        return other

    def get_variants_by_gene(self, gene: str) -> dict:
        """
        Get variants by gene
        """
        return self.get_collection().find({"genes": gene})

    def mark_false_positive_var(self, variant_id: str, fp: bool = True) -> None:
        """
        Mark variant false positive status
        """
        self.mark_false_positive(variant_id, fp)

    def unmark_false_positive_var(self, variant_id: str, fp: bool = False) -> None:
        """
        Unmark variant false positive status
        """
        self.mark_false_positive(variant_id, fp)

    def mark_interesting_var(self, variant_id: str, interesting: bool = True) -> None:
        """
        Mark if the variant is interesting
        """
        self.mark_interesting(variant_id, interesting)

    def unmark_interesting_var(self, variant_id: str, interesting: bool = False) -> None:
        """
        Unmark if the variant is not interesting
        """
        self.mark_interesting(variant_id, interesting)

    def mark_irrelevant_var(self, variant_id: str, irrelevant: bool = True) -> None:
        """
        Mark if the variant is irrelevant
        """
        self.mark_irrelevant(variant_id, irrelevant)

    def unmark_irrelevant_var(self, variant_id: str, irrelevant: bool = False) -> None:
        """
        Unmark if the variant is relevant
        """
        self.mark_irrelevant(variant_id, irrelevant)

    def hide_var_comment(self, id: str, comment_id: str) -> None:
        """
        Hide variant comment
        """
        self.hide_comment(id, comment_id)

    def unhide_variant_comment(self, id: str, comment_id: str) -> None:
        """
        Unhide variant comment
        """
        self.unhide_comment(id, comment_id)

    def add_var_comment(self, id: str, comment: dict) -> None:
        """
        Add variant comment
        """
        self.update_comment(id, comment)

    def hidden_var_comments(self, id: str) -> bool:
        """
        Return True if hidden variant comments else False
        """
        return self.hidden_comments(id)

    def get_total_variant_counts(self) -> int:
        """
        Get total variants count
        """
        return self.get_collection().find().count()

    def get_unique_total_variant_counts(self) -> int:
        """
        Get all unique variants
        """
        query = [
            {"$group": {"_id": {"CHROM": "$CHROM", "POS": "$POS", "REF": "$REF", "ALT": "$ALT"}}},
            {"$group": {"_id": None, "uniqueVariantsCount": {"$sum": 1}}},
            {"$project": {"_id": 0, "uniqueVariantsCount": 1}},
        ]
        try:
            return tuple(self.get_collection().aggregate(query))[0].get("uniqueVariantsCount", 0)
        except:
            return 0

    def get_unique_snp_count(self) -> int:
        """
        Get the count of unique variants where REF and ALT are one of the alphabets A, T, G, C
        """

        query = [
            {
                "$match": {
                    "REF": {"$in": ["A", "T", "G", "C"]},
                    "ALT": {"$in": ["A", "T", "G", "C"]},
                }
            },
            {"$group": {"_id": {"CHROM": "$CHROM", "POS": "$POS", "REF": "$REF", "ALT": "$ALT"}}},
            {"$group": {"_id": None, "uniqueVariantsCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueVariantsCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    def get_unique_fp_count(self) -> int:
        """
        Get the count of unique false positive variants
        """

        query = [
            {"$match": {"fp": True}},
            {"$group": {"_id": {"CHROM": "$CHROM", "POS": "$POS", "REF": "$REF", "ALT": "$ALT"}}},
            {"$group": {"_id": None, "uniqueVariantsCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueVariantsCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0
