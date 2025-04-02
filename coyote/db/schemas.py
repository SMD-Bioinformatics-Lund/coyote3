from coyote.db.base import BaseHandler


class SchemaHandler(BaseHandler):
    """
    SchemaHandler is a class that provides an interface for interacting with the 'schemas' MongoDB collection.
    It extends the BaseHandler class and includes methods for performing CRUD operations and other utility functions
    on schema documents.
    """

    def __init__(self, adapter):
        """
        Initializes the SchemaHandler with a database adapter and sets the collection to 'schemas_collection'.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.schemas_collection)

    def get_all_schemas(self) -> list:
        """
        Retrieves all schema documents from the collection.
        """
        return self.get_collection().find({})

    def get_schema(self, schema_id: str) -> dict:
        """
        Retrieves a single schema document by its unique identifier.
        """
        return self.get_collection().find_one({"_id": schema_id})

    def list_schemas(self, schema_type: str = None) -> list:
        """
        Lists all schema documents of a given type, sorted by schema name. If no type is provided, lists all schemas.
        """
        query = {"schema_type": schema_type} if schema_type else {}
        return list(self.get_collection().find(query).sort("schema_name"))

    def update_schema(self, schema_id, updated_doc):
        """
        Updates an existing schema document identified by its unique identifier with the provided updated document.
        """
        self.get_collection().replace_one({"_id": schema_id}, updated_doc)

    def toggle_active(self, schema_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of a schema document by updating its 'is_active' field.
        """
        return self.get_collection().update_one(
            {"_id": schema_id}, {"$set": {"is_active": active_status}}
        )

    def insert_schema(self, schema_doc: dict):
        """
        Inserts a new schema document into the collection.
        """
        self.get_collection().insert_one(schema_doc)

    def delete_schema(self, schema_id: str):
        """
        Deletes a schema document from the collection by its unique identifier.
        """
        return self.get_collection().delete_one({"_id": schema_id})

    def get_schemas_by_filter(
        self, schema_category: str = None, schema_type: str = None, is_active: bool = True
    ) -> list:
        """
        Get schemas by filter
        """
        query = {"is_active": is_active}
        if schema_category:
            query["schema_category"] = schema_category
        if schema_type:
            query["schema_type"] = schema_type

        return list(self.get_collection().find(query))
