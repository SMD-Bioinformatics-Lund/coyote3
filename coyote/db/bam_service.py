# -*- coding: utf-8 -*-
"""
BamServiceHandler module for Coyote3
====================================

This module defines the `BamServiceHandler` class used for accessing and managing
BAM service data in MongoDB.

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
class BamServiceHandler(BaseHandler):
    """
    Handler for managing BAM service data from the `BAM_Service["samples"]` collection.

    This class provides methods to interact with BAM sample data stored in MongoDB,
    including retrieving BAM file paths for specific sample IDs.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.bam_samples)

    def get_bams(self, sample_ids):
        """
        Retrieve BAM file paths for a list of sample IDs.

        This method queries the `BAM_Service["samples"]` collection to find
        BAM file paths associated with the provided sample IDs.

        Args:
            sample_ids (dict): A dictionary where keys are sample names and
                               values are their corresponding sample IDs.

        Returns:
            dict: A dictionary where keys are sample IDs and values are lists
                  of BAM file paths associated with those IDs.
        """
        bam_id = {}
        for sample in sample_ids:
            bams = list(
                self.get_collection().find({"id": str(sample_ids[sample])})
            )
            for bam in bams:
                if sample_ids[sample] == bam["id"]:
                    if bam["id"] in bam_id:
                        bam_id[bam["id"]].append(bam["bam_path"])
                    else:
                        bam_id[bam["id"]] = [bam["bam_path"]]
                    # bam_id[bam['id']] = bam['bam_path']
        return bam_id
