#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#


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
from api.db.base import BaseHandler


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
