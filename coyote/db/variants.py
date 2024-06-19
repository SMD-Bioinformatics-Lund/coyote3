import pymongo
from bson.objectid import ObjectId
from flask import current_app as app


class VariantsHandler:
    """
    Variants handler from coyote["variants_idref"]
    """

    def get_case_variants(self, query: dict):
        """
        Return variants with according to a constructed varquery
        """
        return self.variants_collection.find(query)

    def get_canonical(self, genes_arr: list) -> dict:
        """
        find canonical transcript for genes
        """
        app.logger.info(f"this is my search string: {genes_arr}")
        canonical_dict = {}
        canonical = self.canonical_collection.find({"gene": {"$in": genes_arr}})

        for c in canonical:
            canonical_dict[c["gene"]] = c["canonical"]

        return canonical_dict

    def get_variant(self, id: str) -> dict:
        """
        Return variant with variant ID
        """
        return self.variants_collection.find_one({"_id": ObjectId(id)})

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

        other_variants = self.variants_collection.find(query).limit(20)

        sample_names = self.samples_collection.find({}, {"_id": 1, "name": 1, "groups": 1})
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

        civic = self.civic_variants_collection.find(
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
        return self.civic_variants_collection.find_one({"name": gene_smbl})

    def get_brca_exchange_data(self, variant, assay) -> dict:
        """
        Return brca data for the variant
        """
        if assay == "gmsonco":
            brca = self.brcaexchange_collection.find_one(
                {
                    "chr38": str(variant["CHROM"]),
                    "pos38": str(variant["POS"]),
                    "ref38": variant["REF"],
                    "alt38": variant["ALT"],
                }
            )
        else:
            brca = self.brcaexchange_collection.find_one(
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
                return self.iarc_tp53_collection.find_one({"var": hgvsc})

        return None

    def is_false_positive(self, variant_id: str, fp: bool) -> None:
        """
        Update variant false positive status
        """
        self.variants_collection.update_one({"_id": ObjectId(variant_id)}, {"$set": {"fp": fp}})
        return None

    def is_interesting(self, variant_id: str, interesting: bool) -> None:
        """
        Update if the variant is interesting or not
        """
        self.variants_collection.update_one(
            {"_id": ObjectId(variant_id)}, {"$set": {"interesting": interesting}}
        )
        return None

    def is_irrelevant(self, variant_id: str, irrelevant: bool) -> None:
        """
        Update if the variant is irrelevant or not
        """
        self.variants_collection.update_one(
            {"_id": ObjectId(variant_id)}, {"$set": {"irrelevant": irrelevant}}
        )
        return None
