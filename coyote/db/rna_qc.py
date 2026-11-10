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
RNAQCHandler module for Coyote3
====================================

This module defines the `RNAQCHandler` class used for accessing and managing
qc data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class RNAQCHandler(BaseHandler):
    """
    Handler for accessing and managing RNA quality control data in MongoDB.
    This class extends the `BaseHandler` to provide specific methods for
    interacting with the RNA QC collection.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.rna_qc_collection)

    def get_rna_qc(self, sample_id: str) -> dict:
        """
        Retrieve qc data for a sample.

        This method queries the `rna_qc` collection in the database to find
        qc data for the provided.

        Args:
            sample_id (str): Sample id to retrieve qc data for that sample.

        Returns:
            dict: qc data for the specified sample.
        """
        doc = self.get_collection().find_one({"SAMPLE_ID": sample_id})

        if not doc:
            return {}

        doc.pop("_id", None)
        return doc
