from coyote.db.base import BaseHandler


class CivicHandler(BaseHandler):
    """
    Civic handler from coyote["civic_variants"], coyote["civic_genes"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.civic_variants_collection)

    def get_civic_data(self, variant: dict, variant_desc: str) -> dict:
        """
        Return civic variant data for the variant/gene
        """

        civic = self.get_collection().find(
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

    def get_civic_gene_info(self, gene_smbl: str) -> dict:
        """
        Return civic gene data for the gene
        """

        return self.adapter.civic_gene_collection.find_one({"name": gene_smbl})
