# -*- coding: utf-8 -*-
"""
ExpressionHandler module for Coyote3
====================================

This module defines the `ExpressionHandler` class used for accessing and managing
expression data in MongoDB.

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
class ExpressionHandler(BaseHandler):
    """
    A handler class for managing expression data in the database.

    This class provides methods to interact with the `expression` collection,
    including retrieving, processing, and managing expression data for transcripts.

    It serves as an interface between the application and the database, ensuring
    efficient querying and data handling for expression-related operations.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.expression_collection)

    def get_expression_data(self, transcripts: list) -> dict:
        """
        Retrieve expression data for a list of transcripts.

        This method queries the `expression` collection in the database to find
        expression data for the provided list of transcript IDs.

        Args:
            transcripts (list): A list of transcript IDs to retrieve expression data for.

        Returns:
            dict: A dictionary where the keys are transcript IDs and the values are
            their corresponding expression data.
        """
        expression = self.get_collection().find({"tid": {"$in": transcripts}})

        expression_dict = {}
        for transcript_expression in expression:
            expression_dict[transcript_expression["tid"]] = (
                transcript_expression["expr"]
            )

        return expression_dict
