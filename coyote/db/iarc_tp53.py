# -*- coding: utf-8 -*-
"""
IARCTP53Handler module for Coyote3
==================================

This module defines the `IARCTP53Handler` class used for accessing and managing
TP53 variant data in MongoDB.

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
class IARCTP53Handler(BaseHandler):
    """
    The `IARCTP53Handler` class is designed to manage and interact with TP53 variant data
    stored in the IARC TP53 collection within a MongoDB database. It extends the functionality
    of the `BaseHandler` class and provides specialized methods for querying, retrieving,
    and processing TP53-related variant information.

    This handler is particularly useful for applications that require access to curated
    TP53 variant data, enabling efficient data retrieval and integration with other
    genomic analysis workflows.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.iarc_tp53_collection)

    def find_iarc_tp53(self, variant: dict) -> dict | None:
        """
        Find IARC TP53 data for a given variant.

        This method checks if the provided variant corresponds to the TP53 gene
        and retrieves the associated data from the IARC TP53 collection in the database.

        Args:
        variant (dict): A dictionary containing variant information, including
                     the `INFO` field with `selected_CSQ` details.

        Returns:
        dict | None: The TP53 variant data if found, otherwise None.
        """
        try:
            if variant["INFO"]["selected_CSQ"]["SYMBOL"] == "TP53":

                hgvsc_parts = variant["INFO"]["selected_CSQ"]["HGVSc"].split(
                    ":"
                )
                if len(hgvsc_parts) >= 2:
                    hgvsc = hgvsc_parts[1]
                else:
                    hgvsc = hgvsc_parts[0]
                return self.get_collection().find_one({"var": hgvsc})
            else:
                return None
        except Exception as e:
            self.app.logger.error(f"Error finding iarc tp53 data: {e}")
            return None
