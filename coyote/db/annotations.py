from coyote.db.base import BaseHandler
from datetime import datetime
from pymongo.results import DeleteResult
from flask import flash


class AnnotationsHandler(BaseHandler):
    """
    Annotations handler from coyote["annotations"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.annotations_collection)

    def get_global_annotations(self, variant, assay, subpanel):
        genomic_location = (
            f"{str(variant['CHROM'])}:{str(variant['POS'])}:{variant['REF']}/{variant['ALT']}"
        )
        if len(variant["INFO"]["selected_CSQ"]["HGVSp"]) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "p",
                                "variant": self.no_transid(
                                    variant["INFO"]["selected_CSQ"]["HGVSp"]
                                ),
                            },
                            {
                                "nomenclature": "c",
                                "variant": self.no_transid(
                                    variant["INFO"]["selected_CSQ"]["HGVSc"]
                                ),
                            },
                            {"nomenclature": "g", "variant": genomic_location},
                        ],
                    }
                )
                .sort("time_created", 1)
            )
        elif len(variant["INFO"]["selected_CSQ"]["HGVSc"]) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "c",
                                "variant": self.no_transid(
                                    variant["INFO"]["selected_CSQ"]["HGVSc"]
                                ),
                            },
                            {"nomenclature": "g", "variant": genomic_location},
                        ],
                    }
                )
                .sort("time_created", 1)
            )
        else:
            annotations = (
                self.get_collection()
                .find({"nomenclature": "g", "variant": genomic_location})
                .sort("time_created", 1)
            )

        latest_classification = {"class": 999}
        latest_classification_other = {}
        annotations_arr = []
        annotations_interesting = {}

        for anno in annotations:
            if "class" in anno:
                ## collect latest for current assay (if latest not assigned pick that)
                ## also collect latest anno for all other assigned assays (including non-assays)
                ## special rule for assays with subpanels, solid, tumwgs maybe lymph?
                try:
                    if assay == "solid":
                        if anno["assay"] == assay and anno["subpanel"] == subpanel:
                            latest_classification = anno
                        else:
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            latest_classification_other[ass_sub] = anno["class"]
                    else:
                        if anno["assay"] == assay:
                            latest_classification = anno
                        else:
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            latest_classification_other[ass_sub] = anno["class"]
                except:
                    latest_classification = anno
                    latest_classification_other["N/A"] = anno["class"]
            elif "text" in anno:
                try:
                    if assay == "solid":
                        if anno["assay"] == assay and anno["subpanel"] == subpanel:
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            annotations_interesting[ass_sub] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                    else:
                        if anno["assay"] == assay:
                            annotations_interesting[anno["assay"]] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                except:
                    annotations_arr.append(anno)

        latest_other_arr = []
        for latest_assay in latest_classification_other:
            assay_sub = latest_assay.split(":")
            try:
                a = assay_sub[1]
            except:
                assay_sub.append(None)
            latest_other_arr.append(
                {
                    "assay": assay_sub[0],
                    "class": latest_classification_other[latest_assay],
                    "subpanel": assay_sub[1],
                }
            )

        return annotations_arr, latest_classification, latest_other_arr, annotations_interesting

    def no_transid(self, nom):
        a = nom.split(":")
        if 1 < len(a):
            return a[1]
        return nom

    def insert_classified_variant(
        self, variant: str, nomenclature: str, class_num: int, variant_data: dict
    ) -> None:
        """
        Insert Classified variant
        """
        if nomenclature != "f":
            if self.get_collection().insert_one(
                {
                    "class": class_num,
                    "author": self.current_user.get_id(),
                    "time_created": datetime.now(),
                    "variant": variant,
                    "nomenclature": nomenclature,
                    "transcript": variant_data.get("transcript", None),
                    "gene": variant_data.get("gene", None),
                    "assay": variant_data.get("assay", None),
                    "subpanel": variant_data.get("subpanel", None),
                }
            ):
                flash("Variant classified", "green")
            else:
                flash("Variant classification failed", "red")
        else:
            if self.get_collection().insert_one(
                {
                    "class": class_num,
                    "author": self.current_user.get_id(),
                    "time_created": datetime.now(),
                    "variant": variant,
                    "nomenclature": nomenclature,
                    "gene1": variant_data.get("gene1", None),
                    "gene2": variant_data.get("gene2", None),
                    "assay": variant_data.get("assay", None),
                    "subpanel": variant_data.get("subpanel", None),
                }
            ):
                flash("Variant classified", "green")
            else:
                flash("Variant classification failed", "red")

        return None

    def delete_classified_variant(
        self, variant: str, nomenclature: str, variant_data: dict
    ) -> list | DeleteResult:
        """
        Delete Classified variant
        """
        num_assay = list(
            self.get_collection().find(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay", None),
                    "gene": variant_data.get("gene", None),
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )
        )
        user_groups = self.current_user.get_groups()
        ## If variant has no match to current assay, it has an historical variant, i.e. not assigned to an assay. THIS IS DANGEROUS, maybe limit to admin?
        if len(num_assay) == 0 and "admin" in user_groups:
            per_assay = list(
                self.get_collection().find(
                    {
                        "class": {"$exists": True},
                        "variant": variant,
                        "gene": variant_data.get("gene", None),
                        "nomenclature": nomenclature,
                    }
                )
            )
        else:
            per_assay = self.get_collection().delete_many(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay", None),
                    "gene": variant_data.get("gene", None),
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )

        return per_assay

    def add_anno_comment(self, comment: dict) -> None:
        """
        Add comment to a variant
        """
        self.add_comment(comment)

    def get_assay_classified_stats(self) -> tuple:
        """
        Get all classified stats
        """
        assay_class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by variant and time_created to ensure the latest document is first
            {"$sort": {"variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "assay": {"$first": "$assay"},
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by assay, nomenclature, and class to get counts
            {
                "$group": {
                    "_id": {"assay": "$assay", "nomenclature": "$nomenclature", "class": "$class"},
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by assay, nomenclature, and class for consistency
            {"$sort": {"_id.assay": 1, "_id.nomenclature": 1, "_id.class": 1}},
        ]
        return list(self.get_collection().aggregate(assay_class_stats_pipeline))

    def get_classified_stats(self) -> tuple:
        """
        Get all classified stats
        """
        class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by nomenclature, variant, and time_created to ensure the latest document is first
            {"$sort": {"nomenclature": 1, "variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by nomenclature and class to get counts
            {
                "$group": {
                    "_id": {"nomenclature": "$nomenclature", "class": "$class"},
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by nomenclature and class for consistency
            {"$sort": {"_id.nomenclature": 1, "_id.class": 1}},
        ]
        return list(self.get_collection().aggregate(class_stats_pipeline))
