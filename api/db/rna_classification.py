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
RNAClassificationHandler module for Coyote3
====================================

This module defines the `RNAClassificationHandler` class used for accessing and managing
classification data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class RNAClassificationHandler(BaseHandler):
    """ """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.rna_classification_collection)

    def get_rna_classification(self, sample_id: str) -> dict:
        """
        Retrieve classification data for a sample.

        This method queries the `rna_classification` collection in the database to find
        classification data for the provided.

        Args:
            sample_id (str): Sample id to retrieve classification data for that sample.

        Returns:
            dict: classification data for the specified sample.
        """
        doc = self.get_collection().find_one({"SAMPLE_ID": sample_id})

        if not doc:
            return {}

        doc.pop("_id", None)
        return doc
