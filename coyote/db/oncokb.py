# -*- coding: utf-8 -*-
"""
OnkoKBHandler module for Coyote3
================================

This module defines the `OnkoKBHandler` class used for accessing and managing
OncoKB data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class OnkoKBHandler(BaseHandler):
    """
    OnkoKBHandler is a class that provides an interface for interacting with the OncoKB data stored in MongoDB collections.

    This class extends the BaseHandler class and includes methods for retrieving annotations, actionable data, and gene
    information from various OncoKB collections. It is designed to facilitate efficient querying and management of
    OncoKB-related data, enabling seamless integration with other components of the `coyote.db` package.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.oncokb_collection)

    def get_oncokb_anno(self, variant: dict, oncokb_hgvsp: str) -> dict:
        """
        Get OncoKB annotation for a variant.

        This method retrieves the OncoKB annotation for a given variant based on its gene and alteration.

        Args:
            variant (dict): A dictionary containing variant information, including the gene symbol.
            oncokb_hgvsp (str): The alteration (HGVSp) to search for in the OncoKB database.

        Returns:
            dict: The OncoKB annotation document if found, otherwise None.
        """
        return self.get_collection().find_one(
            {
                "Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                "Alteration": {"$in": oncokb_hgvsp},
            }
        )

    def get_oncokb_action(self, variant: dict, oncokb_hgvsp: str) -> dict:
        """
        Get OncoKB actionable for a variant.

        This method retrieves actionable OncoKB data for a given variant based on its gene and alteration.

        Args:
            variant (dict): A dictionary containing variant information, including the gene symbol.
            oncokb_hgvsp (str): The alteration (HGVSp) to search for in the actionable OncoKB database.

        Returns:
            dict: A cursor object containing actionable OncoKB documents matching the query.
        """
        return self.adapter.oncokb_actionable_collection.find(
            {
                "Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                "Alteration": {"$in": [oncokb_hgvsp, "Oncogenic Mutations"]},
            }
        )

    def get_oncokb_gene(self, gene: str) -> dict:
        """
        Get OncoKB gene for a given gene.

        This method retrieves the OncoKB gene document for a specified gene from the OncoKB genes collection.

        Args:
            gene (str): The name of the gene to retrieve.

        Returns:
            dict: The OncoKB gene document if found, otherwise None.
        """
        return self.adapter.oncokb_genes_collection.find_one({"name": gene})

    def get_oncokb_action_gene(self,  gene: str) -> dict:
        """
        Get OncoKB actionable for a variant.

        This method retrieves actionable OncoKB data for a given variant based on its gene and alteration.

        Args:
            variant (dict): A dictionary containing variant information, including the gene symbol.
            oncokb_hgvsp (str): The alteration (HGVSp) to search for in the actionable OncoKB database.

        Returns:
            dict: A cursor object containing actionable OncoKB documents matching the query.
        """
        return self.adapter.oncokb_actionable_collection.find_one({"Hugo Symbol": gene})