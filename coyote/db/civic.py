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
CivicHandler module for Coyote3
===============================

This module defines the `CivicHandler` class used for accessing and managing
CIViC variant and gene data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CivicHandler(BaseHandler):
    """
    CivicHandler class for managing CIViC variant and gene data.

    This class provides methods to interact with the CIViC data stored in MongoDB,
    including retrieving variant and gene information. It is designed to work
    with the `coyote["civic_variants"]` and `coyote["civic_genes"]` collections.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.civic_variants_collection)

    def get_civic_data(self, variant: dict, variant_desc: str) -> dict:
        """
        Retrieve CIViC variant data for a given variant or gene.

        This method queries the CIViC variants collection in MongoDB to find
        variant data that matches the provided variant details or gene information.

        Args:
            variant (dict): A dictionary containing variant details, including
                            chromosome (`CHROM`), position (`POS`), alternate
                            allele (`ALT`), and gene information in the `INFO` field.
            variant_desc (str): A string describing the variant.

        Returns:
            dict: A dictionary containing the CIViC variant data that matches
                  the query criteria.
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
                        "hgvs_expressions": variant["INFO"]["selected_CSQ"][
                            "HGVSc"
                        ],
                    },
                    {
                        "gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                        "variant": variant_desc,
                    },
                ]
            }
        )

        return civic

    def get_civic_gene_info(self, gene_smbl: str) -> dict:
        """
        Retrieve CIViC gene data for a specific gene.

        This method queries the `civic_genes` collection in MongoDB to find
        gene data that matches the provided gene symbol.

        Args:
            gene_smbl (str): The symbol of the gene to retrieve data for.

        Returns:
            dict: A dictionary containing the CIViC gene data if found, or None if no match is found.
        """
        return self.adapter.civic_gene_collection.find_one({"name": gene_smbl})
