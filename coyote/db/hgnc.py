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
HGNCHandler module for Coyote3
===============================

This module defines the `HGNCHandler` class used for accessing and managing
HGNC gene data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

from flask import current_app as app

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class HGNCHandler(BaseHandler):
    """
    Handler for managing HGNC gene data stored in the coyote database.

    This class provides methods to interact with HGNC gene information,
    including retrieval, management, and querying of gene metadata.
    It is designed to facilitate efficient access to gene-related data
    for downstream genomic analysis workflows.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.hgnc_collection)

    def get_metadata_by_hgnc_id(self, hgnc_id: str) -> dict:
        """
        Retrieve metadata for a gene using its HGNC ID.

        Args:
            hgnc_id (str): The HGNC ID of the gene.

        Returns:
            dict: The metadata dictionary for the specified gene.
        """
        return self.get_collection().find({"_id": hgnc_id})

    def get_metadata_by_symbol(self, symbol: str) -> dict:
        """
        Retrieve metadata for a gene by its symbol.

        Args:
            symbol (str): The symbol of the gene.

        Returns:
            dict: The metadata of the gene.
        """
        return self.get_collection().find({"hgnc_symbol": symbol})

    def get_metadata_by_symbols(self, symbols: list[str]) -> list[dict]:
        """
        Fetch gene metadata for a list of gene symbols.

        This method retrieves metadata for the provided list of gene symbols.
        If the list is empty, it returns an empty list.

        Args:
            symbols (list[str]): A list of gene symbols to fetch metadata for.

        Returns:
            list[dict]: A list of dictionaries containing gene metadata.
        """
        if not symbols:
            return []
        return self.get_collection().find({"hgnc_symbol": {"$in": symbols}})
