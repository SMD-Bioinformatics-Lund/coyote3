from coyote.db.base import BaseHandler
from datetime import datetime
from bson.objectid import ObjectId


class SchemaHandler(BaseHandler):
    """
    Handler for the 'schemas' MongoDB collection
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.schemas_collection)

    def get_all_schemas(self) -> list:
        """
        Get all the schemas
        """
        return self.get_collection().find({})

    def get_schema(self, schema_name: str) -> dict:
        return self.get_collection().find_one({"_id": schema_name})

    def list_schemas(self, schema_type: str = None) -> list:
        query = {"schema_type": schema_type} if schema_type else {}
        return list(self.get_collection().find(query).sort("schema_name"))

    def upsert_schema(self, schema_data: dict):
        schema_id = schema_data["_id"]
        schema_data["updated_on"] = datetime.utcnow()
        return self.get_collection().replace_one({"_id": schema_id}, schema_data, upsert=True)

    def delete_schema(self, schema_name: str):
        return self.get_collection().delete_one({"_id": schema_name})
