# -*- coding: utf-8 -*-
"""
GroupCoverageHandler module for Coyote3
=======================================

This module defines the `GroupCoverageHandler` class used for managing group coverage
data in MongoDB, including blacklisting and querying functionalities.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

from bson.objectid import ObjectId

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class GroupCoverageHandler(BaseHandler):
    """
    This class provides methods to manage group coverage data in a MongoDB collection.
    It supports operations such as blacklisting genes, regions, and coordinates, querying
    blacklisted entries, checking blacklist status, and removing entries from the blacklist.
    The class is designed to work with a specific MongoDB adapter and collection.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.groupcov_collection)

    def blacklist_coord(
        self, gene: str, coord: str, region: str, group: str
    ) -> dict:
        """
        Blacklist a specific exon, probe, or region for a given gene and group.

        This method checks if the specified combination of gene, coordinate, region,
        and group already exists in the blacklist. If not, it adds the combination
        to the blacklist.

        Args:
            gene (str): The name of the gene to blacklist.
            coord (str): The coordinate of the region to blacklist.
            region (str): The specific region or probe to blacklist.
            group (str): The group or assay associated with the blacklist entry.

        Returns:
            dict: The gene name if the entry was successfully blacklisted,
              or False if the entry already exists.
        """
        data = self.get_collection().find_one(
            {"gene": gene, "group": group, "coord": coord, "region": region}
        )
        if data:
            return False
        else:
            self.get_collection().insert_one(
                {
                    "gene": gene,
                    "group": group,
                    "coord": coord,
                    "region": region,
                }
            )
        return gene

    def blacklist_gene(self, gene: str, group: str) -> dict:
        """
        Blacklist a gene for a specific group.

        This method marks a gene as blacklisted for a given group or assay.
        If the gene is already blacklisted, it returns False. Otherwise, it
        adds the gene to the blacklist.

        Args:
            gene (str): The name of the gene to blacklist.
            group (str): The group or assay associated with the blacklist entry.

        Returns:
            dict: The gene name if the entry was successfully blacklisted,
                  or False if the entry already exists.
        """
        data = self.get_collection().find_one({"gene": gene, "group": group})
        if data:
            return False
        else:
            self.get_collection().insert_one(
                {"gene": gene, "group": group, "region": "gene"}
            )
        return gene

    def get_regions_per_group(self, group: str) -> dict:
        """
        Fetch all blacklisted regions for a specific assay.

        This method retrieves all entries in the blacklist for a given group or assay.

        Args:
            group (str): The group or assay for which to fetch blacklisted regions.

        Returns:
            dict: A cursor object containing all blacklisted regions for the specified group.
        """
        data = self.get_collection().find({"group": group})
        return data

    def is_region_blacklisted(
        self, gene: str, region: str, coord: str, assay: str
    ) -> bool:
        """
        Check if a region is blacklisted for a specific assay.

        This method verifies whether a given combination of gene, region,
        coordinate, and assay is present in the blacklist.

        Args:
            gene (str): The name of the gene to check.
            region (str): The specific region or probe to check.
            coord (str): The coordinate of the region to check.
            assay (str): The assay or group associated with the blacklist entry.

        Returns:
            bool: True if the region is blacklisted for the assay, False otherwise.
        """
        data = self.get_collection().find_one(
            {"gene": gene, "group": assay, "coord": coord, "region": region}
        )
        if data:
            return True
        else:
            return False

    def is_gene_blacklisted(self, gene: str, group: str) -> bool:
        """
        Check if a gene is blacklisted for a specific assay.

        This method verifies whether a given gene is marked as blacklisted
        for a specific group or assay.

        Args:
            gene (str): The name of the gene to check.
            group (str): The group or assay associated with the blacklist entry.

        Returns:
            bool: True if the gene is blacklisted for the assay, False otherwise.
        """
        data = self.get_collection().find_one(
            {"gene": gene, "group": group, "region": "gene"}
        )
        if data:
            return True
        else:
            return False

    def remove_blacklist(self, obj_id: str) -> bool:
        """
        Remove a blacklisted entry by its ObjectId.

        This method deletes a blacklist entry from the collection based on its unique ObjectId.

        Args:
            obj_id (str): The ObjectId of the blacklist entry to remove.

        Returns:
            bool: True if the entry was successfully removed, False otherwise.
        """
        data = self.get_collection().delete_one({"_id": ObjectId(obj_id)})
        if data:
            return True
        else:
            return False
