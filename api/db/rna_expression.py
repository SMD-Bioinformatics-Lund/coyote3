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
RNAExpressionHandler module for Coyote3
====================================

This module defines the `RNAExpressionHandler` class used for accessing and managing
expression data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class RNAExpressionHandler(BaseHandler):
    """
    A handler class for managing expression data in the database.

    This class provides methods to interact with the `rna_expression` collection,
    including retrieving, processing, and managing expression data for a sample.

    It serves as an interface between the application and the database, ensuring
    efficient querying and data handling for rna sample expression-related operations.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.rna_expression_collection)

    def get_rna_expression(self, sample_id: str) -> dict:
        """
        Retrieve expression data for a sample.

        This method queries the `expression` collection in the database to find
        expression data for the provided sample.

        Args:
            sample_id (str): Sample id to retrieve expression data for that sample.

        Returns:
            dict: Expression data for the specified sample.
        """
        doc = self.get_collection().find_one({"SAMPLE_ID": sample_id})

        if not doc:
            return {}

        doc.pop("_id", None)
        return doc
