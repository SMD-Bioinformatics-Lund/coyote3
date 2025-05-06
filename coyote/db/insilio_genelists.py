# -*- coding: utf-8 -*-
# This module provides the `InsilicoGenelistHandler` class for managing in-silico gene lists in a Flask application.

from coyote.db.base import BaseHandler
from typing import Any


class InsilicoGeneListHandler(BaseHandler):
    """
    Coyote gene panels db actions

    This module provides functionality for managing gene panel database actions.
    It includes methods for retrieving, inserting, updating, and deleting gene panel data,
    as well as performing various queries and calculations related to gene panels.
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.insilico_genelist_collection)

    def get_genelist(self, genelist_id: str) -> dict | None:
        """
        Fetch a single gene list.

        This method retrieves a single gene list document from the database
        collection based on the provided `genelist_id`.

        Args:
            genelist_id (str): The unique identifier of the gene list to retrieve.

        Returns:
            dict | None: A dictionary representing the gene list document if found,
            otherwise None.
        """
        return self.get_collection().find_one({"_id": genelist_id})

    def get_all_gene_lists(self) -> list:
        """
        Fetch all gene lists.

        This method retrieves all gene list documents from the database collection,
        excluding the `genes` field. The results are sorted in descending order
        based on the `created_on` field.

        Returns:
            list: A list of all gene list documents from the database.
        """
        return list(
            self.get_collection()
            .find({}, {"genes": 0})
            .sort([("created_on", -1)])
        )

    def insert_genelist(self, config: dict) -> Any:
        """
        Insert a new gene list into the database.

        This method adds a new gene list document to the database collection
        using the provided configuration dictionary.

        Args:
            config (dict): A dictionary containing the gene list data to be inserted.

        Returns:
            pymongo.results.InsertOneResult: The result of the insert operation,
            including the ID of the inserted document.
        """
        return self.get_collection().insert_one(config)

    def update_genelist(self, genelist_id: str, updated_data: dict) -> Any:
        """
        Update an existing gene list.

        This method replaces an existing gene list document in the database
        with the provided updated data, identified by the `genelist_id`.

        Args:
            genelist_id (str): The unique identifier of the gene list to update.
            updated_data (dict): A dictionary containing the updated gene list data.

        Returns:
            Any: The result of the replace operation, typically a `pymongo.results.UpdateResult` object.
        """
        return self.get_collection().replace_one(
            {"_id": genelist_id}, updated_data
        )

    def toggle_genelist_active(
        self, genelist_id: str, active_status: bool
    ) -> bool:
        """
        Toggle the `is_active` field for a gene list.

        This method updates the `is_active` status of a specific gene list
        document in the database, identified by the `genelist_id`.

        Args:
            genelist_id (str): The unique identifier of the gene list to update.
            active_status (bool): The new active status to set for the gene list.

        Returns:
            bool: True if the update operation was acknowledged, otherwise False.
        """
        return self.get_collection().update_one(
            {"_id": genelist_id}, {"$set": {"is_active": active_status}}
        )

    def delete_genelist(self, genelist_id: str) -> Any:
        """
        Delete a gene list.

        This method removes a gene list document from the database collection
        based on the provided `genelist_id`.

        Args:
            genelist_id (str): The unique identifier of the gene list to delete.

        Returns:
            pymongo.results.DeleteResult: The result of the delete operation,
            including information about the deletion.
        """
        return self.get_collection().delete_one({"_id": genelist_id})

    def get_diagnoses_for_assay_panel(self, panel_name: str) -> list[str]:
        """
        Retrieve unique diagnosis terms associated with a specific assay panel.

        This method filters gene lists where the provided `panel_name` is included
        in the `assays` field (a list in the database) and collects all unique
        diagnosis terms.

        Args:
            panel_name (str): The name of the assay panel to filter gene lists by.

        Returns:
            list[str]: A sorted list of unique diagnosis terms associated with the assay panel.
        """
        docs = self.get_collection().find({"assays": panel_name})
        diagnoses = set()
        for doc in docs:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_subpanels_for_assays(self, assay_ids: list[str]) -> list[str]:
        """
        Retrieve unique diagnosis terms associated with a list of assay IDs.

        This method filters gene lists where any of the provided `assay_ids` are included
        in the `assays` field (a list in the database) and collects all unique diagnosis terms.

        Args:
            assay_ids (list[str]): A list of assay IDs to filter gene lists by.

        Returns:
            list[str]: A sorted list of unique diagnosis terms associated with the assay IDs.
        """
        cursor = self.get_collection().find({"assays": {"$in": assay_ids}})
        diagnoses = set()
        for doc in cursor:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_genes_for_subpanel(self, diagnosis_name: str) -> list[str]:
        """
        Retrieve gene symbols associated with a specific subpanel or diagnosis.

        This method queries the database for a document matching the given `diagnosis_name`
        and retrieves the list of gene symbols associated with it.

        Args:
            diagnosis_name (str): The name of the diagnosis or subpanel to query.

        Returns:
            list[str]: A list of gene symbols associated with the specified diagnosis.
            Returns an empty list if no matching document is found.
        """
        doc = self.get_collection().find_one({"diagnosis": diagnosis_name})
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

    def get_all_genes_from_subpanels(self, subpanels) -> list[str]:
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
        for diag in subpanels:
            doc = self.get_collection().find_one({"diagnosis": diag})
            genes.update(doc.get("genes", []))
        return list(genes)

    def get_gene_details_by_symbols(self, symbols: list[str]) -> list[dict]:
        """
        Fetch gene metadata for a list of gene symbols.

        This method retrieves metadata for the provided list of gene symbols.
        If the list is empty, it returns an empty list. The actual database query
        is currently commented out and will need to be enabled when the gene
        collection becomes available.

        Args:
            symbols (list[str]): A list of gene symbols to fetch metadata for.

        Returns:
            list[dict]: A list of dictionaries containing gene metadata. Currently,
            it returns the input list of symbols as a placeholder.
        """
        if not symbols:
            return []

        return list(
            self.adapter.genes_handler.get_metadata_by_symbols(symbols)
        )

    def genelist_exists(
        self,
        genelist_id: str,
        is_active: bool = True,
        diagnosis: str = None,
        list_type: str = None,
        assays: str = None,
        group: str = None,
    ) -> bool:
        """
        Check if a gene list with specific attributes exists in the collection.

        This method queries the database collection to determine if a gene list
        document with the specified attributes exists. The query can include
        optional filters such as `diagnosis`, `list_type`, `assays`, and `group`.

        Args:
            genelist_id (str): The unique identifier of the gene list to check.
            is_active (bool, optional): The active status of the gene list. Defaults to True.
            diagnosis (str, optional): The diagnosis term to filter by. Defaults to None.
            list_type (str, optional): The type of the gene list to filter by. Defaults to None.
            assays (str, optional): The assay name to filter by. Defaults to None.
            group (str, optional): The group name to filter by. Defaults to None.

        Returns:
            bool: True if a matching gene list document exists, otherwise False.
        """
        query = {
            "_id": genelist_id,
            "is_active": is_active,
        }
        if diagnosis:
            query["diagnosis"] = diagnosis
        if list_type:
            query["list_type"] = list_type
        if assays:
            query["assays"] = assays
        if group:
            query["group"] = group
        return self.get_collection().count_documents(query) > 0

    def get_genelists_by_panel(
        self, panel_name: str, active: bool = True
    ) -> list[dict]:
        """
        Retrieve all gene lists associated with a specific panel.

        This method queries the database collection for gene lists that match the
        specified panel name and active status. It excludes certain fields from
        the returned documents to reduce the payload size.

        Args:
            panel_name (str): The name of the panel to filter gene lists by.
            active (bool, optional): The active status of the gene lists to filter by.
                Defaults to True.

        Returns:
            list[dict]: A list of dictionaries representing the gene lists that match
            the query, with selected fields excluded.
        """
        projection = {
            "genes": 0,
            "created_on": 0,
            "created_by": 0,
            "changelog": 0,
            "schema_version": 0,
            "schema_name": 0,
            "is_active": 0,
        }
        query = {"assays": panel_name, "is_active": active}
        return list(self.get_collection().find(query, projection))

    def get_genelists_ids(
        self,
        panel_name: str,
        diagnosis: str,
        list_type: str,
        active: bool = True,
    ) -> list[str]:
        """
        Retrieve all gene list IDs associated with a specific panel.

        This method queries the database collection for gene lists that match the
        specified panel name, diagnosis, list type, and active status. It returns
        a list of IDs for the matching gene lists.

        Args:
            panel_name (str): The name of the panel to filter gene lists by.
            diagnosis (str): The diagnosis term to filter gene lists by.
            list_type (str): The type of the gene list to filter by.
            active (bool, optional): The active status of the gene lists to filter by.
                Defaults to True.

        Returns:
            list[str]: A list of string representations of the IDs for the matching
            gene lists.
        """
        query = {
            "assays": panel_name,
            "diagnosis": diagnosis,
            "list_type": list_type,
            "is_active": active,
        }
        projection = {"_id": 1}
        return [
            str(doc["_id"])
            for doc in self.get_collection().find(query, projection)
        ]

    def get_genelist_docs_by_ids(self, genelist_ids: list) -> dict:
        """
        Retrieve selected fields from genelist documents for given IDs.

        This method queries the database collection for documents with IDs matching
        the provided `genelist_ids`. It retrieves only the specified fields and
        formats the result as a dictionary where the keys are the document IDs and
        the values are the remaining fields.

        Args:
            genelist_ids (list): A list of gene list IDs to query.

        Returns:
            dict: A dictionary where the keys are the IDs of the gene lists and the
            values are dictionaries containing the selected fields. Returns an empty
            dictionary if `genelist_ids` is empty.
        """
        if not genelist_ids:
            return {}

        # Define the fields to include in the query result
        projection = {"_id": 1, "is_active": 1, "displayname": 1, "genes": 1}

        # Query the database for documents with matching IDs
        cursor = self.get_collection().find(
            {"_id": {"$in": genelist_ids}}, projection
        )

        # Format the result as a dictionary with IDs as keys
        return {doc.pop("_id"): doc for doc in cursor}
