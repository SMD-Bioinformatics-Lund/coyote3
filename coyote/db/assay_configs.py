from coyote.db.base import BaseHandler
from typing import Any
from pymongo import cursor


class AssayConfigsHandler(BaseHandler):
    """
    AssayConfigsHandler is a class responsible for managing assay configuration data
    stored in a MongoDB collection. It provides methods to perform CRUD operations
    on assay configurations, as well as additional functionality to retrieve specific
    data and toggle the active status of an assay configuration.
    """

    def __init__(self, adapter):
        """
        Initializes the handler with a database adapter and sets the collection to the assay_configs_collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.assay_configs_collection)

    def get_all_assay_configs(self) -> cursor.Cursor:
        """
        Retrieves a list of all available assay names from the collection.
        """
        return self.get_collection().find({})

    def get_assay_names(self) -> dict:
        """
        Retrieves a specific assay configuration document by its ID.
        """
        assays = self.get_collection().find({}, {"assay_name": 1})
        return [a["assay_name"] for a in assays]

    def get_assay_config(self, assay_id: str) -> dict:
        """
        Retrieves a specific assay configuration document by its ID.
        """
        return self.get_collection().find_one({"_id": assay_id})

    def update_assay_config(self, assay_id: str, data: dict) -> Any:
        """
        Updates an existing assay configuration document with new data.
        """
        return self.get_collection().update_one({"_id": assay_id}, {"$set": data})

    def insert_assay_config(self, data: dict) -> Any:
        """
        Inserts a new assay configuration document into the collection.
        """
        return self.get_collection().insert_one(data)

    def delete_assay_config(self, assay_id: str) -> Any:
        """
        Deletes an assay configuration document by its ID.
        """
        return self.get_collection().delete_one({"_id": assay_id})

    def toggle_active(self, assay_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of an assay configuration document by updating its 'is_active' field.
        """
        return self.get_collection().update_one(
            {"_id": assay_id}, {"$set": {"is_active": active_status}}
        )
