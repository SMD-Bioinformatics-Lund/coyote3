import pymongo
from bson.objectid import ObjectId
from flask import current_app as app
from flask_login import current_user
from datetime import datetime
from coyote.db.base import BaseHandler


class VariantsHandler(BaseHandler):
    """
    Variants handler from coyote["variants_idref"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        print(f"Inside SNVs: {self.adapter}")
        print(f"Inside SNVs: {self.adapter.client}")
        print(f"Inside SNVs: {self.adapter.variants_collection}")
        self.handler_collection = self.adapter.variants_collection

    def get_case_variants(self, query: dict):
        """
        Return variants with according to a constructed varquery
        """
        return self.handler_collection.find(query)

    def get_canonical(self, genes_arr: list) -> dict:
        """
        find canonical transcript for genes
        """
        app.logger.info(f"this is my search string: {genes_arr}")
        canonical_dict = {}
        canonical = self.adapter.canonical_collection.find({"gene": {"$in": genes_arr}})

        for c in canonical:
            canonical_dict[c["gene"]] = c["canonical"]

        return canonical_dict

    def get_variant(self, id: str) -> dict:
        """
        Return variant with variant ID
        """
        return self.handler_collection.find_one({"_id": ObjectId(id)})

    def get_variant_in_other_samples(self, variant, assay=None) -> dict:
        """
        Return same variant from other samples of a specific assay
        """
        query = {
            "CHROM": variant["CHROM"],
            "POS": variant["POS"],
            "REF": variant["REF"],
            "ALT": variant["ALT"],
            "SAMPLE_ID": {"$ne": variant["SAMPLE_ID"]},
        }

        other_variants = self.handler_collection.find(query).limit(20)

        sample_names = self.adapter.samples_collection.find({}, {"_id": 1, "name": 1, "groups": 1})
        name = {}
        for samp in sample_names:
            name[str(samp["_id"])] = samp["name"]

        other = []
        for var in other_variants:
            var["sample_name"] = name.get(var["SAMPLE_ID"], "unknown")
            other.append(var.copy())

        return other

    def get_civic_data(self, variant, variant_desc) -> dict:
        """
        Return civic variant data for the s
        """

        civic = self.adapter.civic_variants_collection.find(
            {
                "$or": [
                    {
                        "chromosome": str(variant["CHROM"]),
                        "start": str(variant["POS"]),
                        "variant_bases": variant["ALT"],
                    },
                    {
                        "gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                        "hgvs_expressions": variant["INFO"]["selected_CSQ"]["HGVSc"],
                    },
                    {"gene": variant["INFO"]["selected_CSQ"]["SYMBOL"], "variant": variant_desc},
                ]
            }
        )

        return civic

    def get_civic_gene(self, gene_smbl) -> dict:
        return self.adapter.civic_variants_collection.find_one({"name": gene_smbl})

    def get_brca_exchange_data(self, variant, assay) -> dict:
        """
        Return brca data for the variant
        """
        if assay == "gmsonco":
            brca = self.adapter.brcaexchange_collection.find_one(
                {
                    "chr38": str(variant["CHROM"]),
                    "pos38": str(variant["POS"]),
                    "ref38": variant["REF"],
                    "alt38": variant["ALT"],
                }
            )
        else:
            brca = self.adapter.brcaexchange_collection.find_one(
                {
                    "chr": str(variant["CHROM"]),
                    "pos": str(variant["POS"]),
                    "ref": variant["REF"],
                    "alt": variant["ALT"],
                }
            )

        return brca

    def find_iarc_tp53(self, variant) -> dict | None:
        """
        Find iarc tp53 data
        """
        if variant["INFO"]["selected_CSQ"]["SYMBOL"] == "TP53":
            hgvsc_parts = variant["INFO"]["selected_CSQ"]["HGVSc"].split(":")
            if len(hgvsc_parts) >= 2:
                hgvsc = hgvsc_parts[1]
                return self.adapter.iarc_tp53_collection.find_one({"var": hgvsc})

        return None

    def insert_classified_variant(
        self, variant: str, nomenclature: str, class_num: int, variant_data: dict
    ) -> None:
        """
        Insert Classified variant
        """
        if nomenclature != "f":
            self.adapter.annotations_collection.insert_one(
                {
                    "class": class_num,
                    "author": current_user.get_id(),
                    "time_created": datetime.now(),
                    "variant": variant,
                    "nomenclature": nomenclature,
                    "transcript": variant_data.get("transcript", None),
                    "gene": variant_data.get("gene", None),
                    "assay": variant_data.get("assay", None),
                    "subpanel": variant_data.get("subpanel", None),
                }
            )
        else:
            self.adapter.annotations_collection.insert_one(
                {
                    "class": class_num,
                    "author": current_user.get_id(),
                    "time_created": datetime.now(),
                    "variant": variant,
                    "nomenclature": nomenclature,
                    "gene1": variant_data.get("gene1", None),
                    "gene2": variant_data.get("gene2", None),
                    "assay": variant_data.get("assay", None),
                    "subpanel": variant_data.get("subpanel", None),
                }
            )
        return None

    def delete_classified_variant(
        self, variant: str, nomenclature: str, variant_data: dict
    ) -> list | pymongo.results.DeleteResult:
        """
        Delete Classified variant
        """
        num_assay = list(
            self.adapter.annotations_collection.find(
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
        user_groups = current_user.get_groups()
        ## If variant has no match to current assay, it has an historical variant, i.e. not assigned to an assay. THIS IS DANGEROUS, maybe limit to admin?
        if len(num_assay) == 0 and "admin" in user_groups:
            per_assay = list(
                self.adapter.annotations_collection.find(
                    {
                        "class": {"$exists": True},
                        "variant": variant,
                        "gene": variant_data.get("gene", None),
                        "nomenclature": nomenclature,
                    }
                )
            )
        else:
            per_assay = self.adapter.annotations_collection.delete_many(
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
        self.mark_irrelevant(variant_id, interesting)

    def unmark_interesting_var(self, variant_id: str, interesting: bool = False) -> None:
        """
        Unmark if the variant is not interesting
        """
        self.mark_irrelevant(variant_id, interesting)

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
