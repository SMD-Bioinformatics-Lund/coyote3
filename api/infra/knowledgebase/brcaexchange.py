"""
BRCAHandler module for Coyote3
==============================

This module defines the `BRCAHandler` class used for accessing and managing
BRCA data in MongoDB.
It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.mongo.handlers.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BRCAHandler(BaseHandler):
    """
    The `BRCAHandler` class provides functionality for accessing and managing
    BRCA-related data stored in the `brcaexchange` collection of MongoDB.

    This class extends the `BaseHandler` and includes methods for querying
    BRCA variant data based on specific assay types.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.brcaexchange_collection)

    def ensure_indexes(self) -> None:
        """Create indexes used by BRCA exchange coordinate lookups."""
        col = self.get_collection()
        col.create_index(
            [("chr", 1), ("pos", 1), ("ref", 1), ("alt", 1)],
            name="chr_pos_ref_alt",
            background=True,
        )
        col.create_index(
            [("chr38", 1), ("pos38", 1), ("ref38", 1), ("alt38", 1)],
            name="chr38_pos38_ref38_alt38",
            background=True,
        )

    def get_brca_data(self, variant: dict, assay: str) -> dict:
        """
        Retrieve BRCA data for a specific variant.

        This method queries the `brcaexchange` collection in MongoDB to find BRCA-related
        data that matches the provided variant details.

        Args:
            variant (dict): A dictionary containing variant details, including
                            chromosome (`CHROM`), position (`POS`), reference allele (`REF`),
                            and alternate allele (`ALT`).
            assay (str): The assay type to use for querying the data. If the assay is
                         "gmsonco", the query will use GRCh38 coordinates (`chr38`, `pos38`, etc.).
                         Otherwise, it will use standard coordinates (`chr`, `pos`, etc.).

        Returns:
            dict: A dictionary containing the BRCA data that matches the query criteria,
                  or `None` if no match is found.
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
