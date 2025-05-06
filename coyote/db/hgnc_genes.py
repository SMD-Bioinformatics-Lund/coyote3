# -*- coding: utf-8 -*-
"""
GenesHandler module for Coyote3
===============================

This module defines the `GenesHandler` class used for accessing and managing
HGNC gene data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from flask import current_app as app


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class GenesHandler(BaseHandler):
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
        self.set_collection(self.adapter.hgnc_genes_collection)

    def get_gene_metadata(self, hgnc_id):
        return self.get_collection().find({"_id": hgnc_id})

    def get_metadata_by_symbol(self, symbol):
        """
        Retrieve metadata for a gene by its symbol.

        Args:
            symbol (str): The symbol of the gene.

        Returns:
            dict: The metadata of the gene.
        """
        return self.get_collection().find({"hgnc_symbol": symbol})

    def get_metadata_by_symbols(self, symbols):
        """
        Retrieve metadata for multiple genes by their symbols.

        Args:
            symbols (list): A list of gene symbols.

        Returns:
            list: A list of metadata dictionaries for the genes.
        """
        return self.get_collection().find({"hgnc_symbol": {"$in": symbols}})
