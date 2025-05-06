# -*- coding: utf-8 -*-
# This file contains the GenesHandler class for managing HGNC gene data.

from coyote.db.base import BaseHandler
from flask import current_app as app


class GenesHandler(BaseHandler):
    """
    Handler for managing HGNC gene data stored in the coyote database.

    This class provides methods to interact with HGNC gene information,
    including retrieval and management of gene metadata.
    """

    def __init__(self, adapter):
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
