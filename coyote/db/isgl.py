# -*- coding: utf-8 -*-
"""
ISGLHandler module for Coyote3
==========================================

This module defines the `ISGLHandler` class used for accessing and managing
gene panel data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from typing import Any


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ISGLHandler(BaseHandler):
    """
    Coyote in silico gene panels database handler

    This class provides a comprehensive interface for managing gene panel data in the database.
    It supports operations such as retrieving, inserting, updating, and deleting gene panel records.
    Additionally, it includes methods for performing advanced queries, filtering, and calculations
    related to gene panels, assays, diagnoses, and associated metadata.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.insilico_genelist_collection)

    def get_isgl(
        self, isgl_id: str, is_active: bool | None = None
    ) -> dict | None:
        """
        Fetch a single gene list.

        This method retrieves a single gene list document from the database
        collection based on the provided `isgl_id`.

        Args:
            isgl_id (str): The unique identifier of the gene list to retrieve.
            is_active (bool): Optional; if True, only active gene lists are considered.

        Returns:
            dict | None: A dictionary representing the gene list document if found,
            otherwise None.
        """
        query = {"_id": isgl_id}
        if is_active is not None:
            query["is_active"] = is_active
        return self.get_collection().find_one(query)

    def get_all_isgl(self, is_active: bool | None = None) -> list:
        """
        Fetch all gene lists.

        This method retrieves all gene list documents from the database collection,
        excluding the `genes` field. The results are sorted in descending order
        based on the `created_on` field.

        Returns:
            list: A list of all gene list documents from the database.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return list(
            self.get_collection()
            .find(query, {"genes": 0})
            .sort([("created_on", -1)])
        )

    def create_isgl(self, data: dict) -> Any:
        """
        Insert a new gene list into the database.

        This method adds a new gene list document to the database collection
        using the provided configuration dictionary.

        Args:
            data (dict): A dictionary containing the gene list data to be inserted.

        Returns:
            pymongo.results.InsertOneResult: The result of the insert operation,
            including the ID of the inserted document.
        """
        return self.get_collection().insert_one(data)

    def update_isgl(self, isgl_id: str, updated_data: dict) -> Any:
        """
        Update an existing gene list.

        This method replaces an existing gene list document in the database
        with the provided updated data, identified by the `isgl_id`.

        Args:
            isgl_id (str): The unique identifier of the gene list to update.
            updated_data (dict): A dictionary containing the updated gene list data.

        Returns:
            Any: The result of the replace operation, typically a `pymongo.results.UpdateResult` object.
        """
        return self.get_collection().replace_one(
            {"_id": isgl_id}, updated_data
        )

    def toggle_isgl_active(self, isgl_id: str, active_status: bool) -> bool:
        """
        Toggle the `is_active` field for a gene list.

        This method updates the `is_active` status of a specific gene list
        document in the database, identified by the `isgl_id`.

        Args:
            isgl_id (str): The unique identifier of the gene list to update.
            active_status (bool): The new active status to set for the gene list.

        Returns:
            bool: True if the update operation was acknowledged, otherwise False.
        """
        return self.toggle_active(isgl_id, active_status)

    def delete_isgl(self, isgl_id: str) -> Any:
        """
        Delete a gene list.

        This method removes a gene list document from the database collection
        based on the provided `isgl_id`.

        Args:
            isgl_id (str): The unique identifier of the gene list to delete.

        Returns:
            pymongo.results.DeleteResult: The result of the delete operation,
            including information about the deletion.
        """
        return self.get_collection().delete_one({"_id": isgl_id})

    def get_subpanels_for_asp(self, asp_names: list[str]) -> list[str]:
        """
        Retrieve unique diagnosis terms associated with a list of assay IDs.

        This method filters gene lists where any of the provided `asp_names` are included
        in the `assays` field (a list in the database) and collects all unique diagnosis terms.

        Args:
            asp_names (list[str]): A list of assay IDs to filter gene lists by.

        Returns:
            list[str]: A sorted list of unique diagnosis terms associated with the assay IDs.
        """
        cursor = self.get_collection().find({"assays": {"$in": asp_names}})
        diagnoses = set()
        for doc in cursor:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_asp_subpanel_genes(
        self, asp_name: str, subpanel: str
    ) -> list[str]:
        """
        Retrieve gene symbols for a specific subpanel (diagnosis) within an assay.

        Queries the database for a document where the given `asp_name` is present in the `assays` field
        and the `diagnosis` field matches the provided `subpanel`. Returns the list of gene symbols
        associated with that subpanel.

        Args:
            asp_name (str): The assay ID to filter by.
            subpanel (str): The diagnosis or subpanel name to query.

        Returns:
            list[str]: List of gene symbols for the specified subpanel, or an empty list if not found.
        """
        doc = self.get_collection().find_one(
            {"assays": asp_name, "diagnosis": subpanel}
        )
        return doc.get("genes", []) if doc else []

    def get_all_subpanels(self) -> list[str]:
        """
        Retrieve all unique subpanels (diagnosis terms) from the database.

        This method queries the database collection for all documents and extracts
        the `diagnosis` field, which is expected to be a list. It then flattens
        and sorts all the unique diagnosis terms.

        Returns:
            list[str]: A sorted list of all unique diagnosis terms (subpanels)
            found in the database.
        """
        return sorted(
            d
            for doc in self.get_collection().find({})
            for d in doc.get("diagnosis", [])
        )

    def get_all_subpanel_genes(self, subpanels) -> list[str]:
        """
        Retrieve all unique genes from a list of subpanels.

        This method iterates through the provided list of subpanels (diagnosis terms),
        queries the database for each subpanel, and collects all associated genes.
        The resulting list of genes is flattened and deduplicated.

        Args:
            subpanels (list[str]): A list of subpanel names (diagnosis terms) to query.

        Returns:
            list[str]: A list of unique gene symbols associated with the provided subpanels.
        """
        genes = set()
        docs = self.get_collection().find(
            {"diagnosis": {"$in": subpanels}}, {"genes": 1}
        )
        for doc in docs:
            genes.update(doc.get("genes", []))
        return list(genes)

    def isgl_exists(
        self,
        isgl_id: str,
        is_active: bool = True,
    ) -> bool:
        """
        Check if a gene list with specific attributes exists in the collection.

        This method queries the database collection to determine if a gene list
        document with the specified attributes exists. The query can include
        optional filters such as `diagnosis`, `list_type`, `assays`, and `group`.

        Args:
            isgl_id (str): The unique identifier of the gene list to check.
            is_active (bool, optional): The active status of the gene list. Defaults to True.

        Returns:
            bool: True if a matching gene list document exists, otherwise False.
        """
        query = {
            "_id": isgl_id,
            "is_active": is_active,
        }
        return self.get_collection().count_documents(query) > 0

    def get_isgl_by_asp(
        self, asp_name: str, is_active: bool | None = None
    ) -> list[dict]:
        """
        Retrieve all gene lists associated with a specific assay panel.

        This method queries the database collection for gene lists that match the
        specified panel name and active status. It excludes certain fields from
        the returned documents to reduce the payload size.

        Args:
            asp_name (str): The name of the assay specific panel to filter gene lists by.
            is_active (bool, optional): The active status of the gene lists to filter by.
                Defaults to True.

        Returns:
            list[dict]: A list of dictionaries representing the gene lists that match
            the query, with selected fields excluded.
        """
        query = {"assays": asp_name}
        if is_active is not None:
            query["is_active"]: is_active
        projection = {
            "genes": 0,
            "created_on": 0,
            "created_by": 0,
            "changelog": 0,
            "schema_version": 0,
            "schema_name": 0,
            "is_active": 0,
        }

        return list(self.get_collection().find(query, projection))

    def get_isgl_ids(
        self,
        asp_name: str,
        subpanel: str,
        list_type: str,
        is_active: bool | None = None,
    ) -> list[str]:
        """
        Retrieve all gene list IDs associated with a specific panel.

        This method queries the database collection for gene lists that match the
        specified panel name, diagnosis, list type, and active status. It returns
        a list of IDs for the matching gene lists.

        Args:
            asp_name (str): The name of the panel to filter gene lists by.
            subpanel (str): The diagnosis term to filter gene lists by.
            list_type (str): The type of the gene list to filter by.
            is_active (bool, optional): The active status of the gene lists to filter by.
                Defaults to True.

        Returns:
            list[str]: A list of string representations of the IDs for the matching
            gene lists.
        """
        query = {
            "assays": asp_name,
            "diagnosis": subpanel,
            "list_type": list_type,
        }
        if is_active is not None:
            query["is_active"] = is_active
        projection = {"_id": 1}
        return [
            str(doc["_id"])
            for doc in self.get_collection().find(query, projection)
        ]

    def get_isgl_by_ids(self, isgl_ids: list) -> dict:
        """
        Retrieve selected fields from genelist documents for given IDs.

        This method queries the database collection for documents with IDs matching
        the provided `isgl_ids`. It retrieves only the specified fields and
        formats the result as a dictionary where the keys are the document IDs and
        the values are the remaining fields.

        Args:
            isgl_ids (list): A list of gene list IDs to query.

        Returns:
            dict: A dictionary where the keys are the IDs of the gene lists and the
            values are dictionaries containing the selected fields. Returns an empty
            dictionary if `isgl_ids` is empty.
        """
        if not isgl_ids:
            return {}

        # Define the fields to include in the query result
        projection = {"_id": 1, "is_active": 1, "displayname": 1, "genes": 1}

        # Query the database for documents with matching IDs
        cursor = self.get_collection().find(
            {"_id": {"$in": isgl_ids}}, projection
        )

        # Format the result as a dictionary with IDs as keys
        return {doc.pop("_id"): doc for doc in cursor}
