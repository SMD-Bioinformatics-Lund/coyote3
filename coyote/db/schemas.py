# -*- coding: utf-8 -*-
"""
SchemaHandler module for Coyote3
================================

This module defines the `SchemaHandler` class used for accessing and managing
schema data in MongoDB.

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
class SchemaHandler(BaseHandler):
    """
    SchemaHandler is a class that provides an interface for interacting with the schemas data in the MongoDB collection.

    This class extends the BaseHandler class and provides methods for performing CRUD operations, toggling schema states,
    and filtering schema documents based on various criteria. It is designed to simplify schema management and ensure
    efficient interaction with the MongoDB collection storing schema data.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.schemas_collection)

    def get_all_schemas(self) -> Any:
        """
        Retrieves all schema documents from the collection.

        Returns:
            Any: A cursor or iterable containing all schema documents.
        """
        return self.get_collection().find({})

    def get_schema(self, schema_id: str) -> dict:
        """
        Retrieves a single schema document by its unique identifier.

        Args:
            schema_id (str): The unique identifier of the schema to retrieve.

        Returns:
            dict: The schema document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": schema_id})

    def list_schemas(self, schema_type: str = None) -> list:
        """
        Lists all schema documents of a given type, sorted by schema name in ascending order.

        Args:
            schema_type (str, optional): The type of schema to filter by. Defaults to None.

        Returns:
            list: A list of schema documents matching the specified type, sorted by schema name.
        """
        query = {"schema_type": schema_type} if schema_type else {}
        return list(self.get_collection().find(query).sort("schema_name"))

    def update_schema(self, schema_id, updated_doc) -> Any:
        """
        Updates an existing schema document identified by its unique identifier with the provided updated document.

        Args:
            schema_id (str): The unique identifier of the schema to update.
            updated_doc (dict): The updated schema document.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().replace_one(
            {"_id": schema_id}, updated_doc
        )

    def toggle_active(self, schema_id: str, active_status: bool) -> Any:
        """
        Toggles the active status of a schema document.

        Args:
            schema_id (str): The unique identifier of the schema to update.
            active_status (bool): The new active status to set for the schema.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().update_one(
            {"_id": schema_id}, {"$set": {"is_active": active_status}}
        )

    def insert_schema(self, schema_doc: dict) -> Any:
        """
        Inserts a new schema document into the collection.

        Args:
            schema_doc (dict): The schema document to insert.

        Returns:
            Any: The result of the insert operation.
        """
        self.get_collection().insert_one(schema_doc)

    def delete_schema(self, schema_id: str) -> Any:
        """
        Deletes a schema document from the collection by its unique identifier.

        Args:
            schema_id (str): The unique identifier of the schema to delete.

        Returns:
            Any: The result of the delete operation.
        """
        return self.get_collection().delete_one({"_id": schema_id})

    def get_schemas_by_filter(
        self,
        schema_category: str = None,
        schema_type: str = None,
        is_active: bool = True,
    ) -> list:
        """
        Retrieves schema documents based on the provided filters.

        Args:
            schema_category (str, optional): The category of the schema to filter by. Defaults to None.
            schema_type (str, optional): The type of the schema to filter by. Defaults to None.
            is_active (bool, optional): Whether to filter by active schemas. Defaults to True.

        Returns:
            list: A list of schema documents matching the provided filters.
        """
        query = {"is_active": is_active}
        if schema_category:
            query["schema_category"] = schema_category
        if schema_type:
            query["schema_type"] = schema_type

        return list(self.get_collection().find(query))
