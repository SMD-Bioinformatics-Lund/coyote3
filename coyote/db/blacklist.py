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
BlacklistHandler module for Coyote3
===================================

This module defines the `BlacklistHandler` class used for accessing and managing
blacklist data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app
from coyote.util.common_utility import CommonUtility


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BlacklistHandler(BaseHandler):
    """
    The `BlacklistHandler` class provides methods to manage and interact with
    blacklist data stored in the MongoDB database. It allows adding blacklist
    information to variants, inserting new blacklist entries, and retrieving
    unique blacklist counts.

    This class is part of the `coyote.db` package and extends the functionality
    of the `BaseHandler` class.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.blacklist_collection)

    def add_blacklist_data(self, variants: list, assay: str) -> dict:
        """
        Add blacklist data to variants.

        This method enriches a list of variants with blacklist data from the database.
        It checks if each variant's `simple_id` exists in the blacklist collection
        for the specified assay and adds the corresponding `in_normal_perc` value
        to the variant if found.

        Args:
            variants (list): A list of variant dictionaries, each containing a `simple_id` key.
            assay (str): The assay type used to filter blacklist data.

        Returns:
            list: The updated list of variants with blacklist data added where applicable.
        """
        short_pos = [var.get("simple_id") for var in variants]

        blacklisted = self.get_collection().find(
            {"assay": assay, "pos": {"$in": short_pos}},
            {"pos": 1, "in_normal_perc": 1, "_id": 0},
        )
        blacklisted_dict = {
            elem["pos"]: elem["in_normal_perc"] for elem in list(blacklisted)
        }

        for var in variants:
            if var["simple_id"] in blacklisted_dict:
                var["blacklist"] = blacklisted_dict[var["simple_id"]]

        return variants

    def blacklist_variant(self, var: dict, assay: str) -> str:
        """
        Add a variant to the blacklist collection.

        This method inserts a variant into the blacklist collection in the database.
        It uses the `simple_id` of the variant to identify it and associates it with
        the specified assay. If the insertion is successful, a success message is flashed;
        otherwise, an error message is flashed.

        Args:
            var (dict): A dictionary containing variant details. If `simple_id` is not
                        present, it will be generated using `CommonUtility.get_simple_id`.
            assay (str): The assay type to associate with the variant.

        Returns:
            str: A success message if the variant is added successfully, or an error
                 message if the insertion fails.
        """
        short_pos = var.get("simple_id", CommonUtility.get_simple_id(var))

        if self.get_collection().insert_one(
            {"assay": assay, "in_normal_perc": 1, "pos": short_pos}
        ):
            flash(f"Variant {short_pos} added to blacklist", "green")
            return True
        else:
            flash(f"Failed to add variant {short_pos} to blacklist", "red")
            return False

    def get_unique_blacklist_count(self) -> int:
        """
        Get the count of unique blacklist entries.

        This method aggregates the blacklist collection to count the number of unique
        blacklist entries based on the `pos` field.

        Returns:
            int: The count of unique blacklist entries. Returns 0 if no entries are found
                 or if an error occurs during the aggregation.
        """
        query = [
            {"$group": {"_id": {"pos": "$pos"}}},
            {"$group": {"_id": None, "uniqueBlacklistCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueBlacklistCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0
