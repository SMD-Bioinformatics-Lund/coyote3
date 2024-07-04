from coyote.db.base import BaseHandler


class BRCAHandler(BaseHandler):
    """
    BRCA handler from coyote["brcaexchange"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.brcaexchange_collection)

    def get_brca_data(self, variant: dict, assay: str) -> dict:
        """
        Return brca data for the variant
        """
        if assay == "gmsonco":
            brca = self.get_collection().find_one(
                {
                    "chr38": str(variant["CHROM"]),
                    "pos38": str(variant["POS"]),
                    "ref38": variant["REF"],
                    "alt38": variant["ALT"],
                }
            )
        else:
            brca = self.get_collection().find_one(
                {
                    "chr": str(variant["CHROM"]),
                    "pos": str(variant["POS"]),
                    "ref": variant["REF"],
                    "alt": variant["ALT"],
                }
            )

        return brca
