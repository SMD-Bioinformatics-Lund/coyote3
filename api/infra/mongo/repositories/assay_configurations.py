"""
ASPConfigRepository module for Coyote3
======================================

This module defines the `ASPConfigRepository` class used for accessing and managing
assay configuration data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import re

from pymongo import cursor

from api.config.constants import SUBPANEL_BASE_ID, normalize_environment, validate_identifier
from api.contracts.operations import OperationResult
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.infra.mongo.repositories.base import BaseRepository


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ASPConfigRepository(BaseRepository):
    """
    ASPConfigRepository is a class responsible for managing assay configuration data
    stored in a MongoDB collection. It provides methods to perform CRUD operations
    on assay configurations, retrieve specific data, toggle the active status of an
    assay configuration, and manage assay groups and mappings. This class serves as
    a key component for handling assay-related data efficiently in the database.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.aspc_collection)

    def ensure_indexes(self) -> None:
        """
        Create minimal indexes for ASPC filter/distinct paths.
        """
        col = self.get_collection()
        existing = {index["name"] for index in col.list_indexes()}
        for legacy_name in ("aspc_id_1", "asp_subpanel_environment_unique"):
            if legacy_name in existing:
                col.drop_index(legacy_name)
        col.create_index(
            [("aspc_id", 1), ("is_active", 1)],
            name="aspc_id_active_1",
            unique=True,
            background=True,
            partialFilterExpression={
                "aspc_id": {"$exists": True, "$type": "string"},
                "is_active": True,
            },
        )
        col.create_index(
            [("is_active", 1), ("asp_id", 1), ("subpanel_id", 1), ("environment", 1)],
            name="is_active_asp_subpanel_environment",
            background=True,
        )
        col.create_index(
            [("asp_id", 1), ("subpanel_id", 1), ("environment", 1), ("is_active", 1)],
            name="asp_subpanel_environment_active_1",
            unique=True,
            background=True,
            partialFilterExpression={
                "asp_id": {"$exists": True, "$type": "string"},
                "subpanel_id": {"$exists": True, "$type": "string"},
                "environment": {"$exists": True, "$type": "string"},
                "is_active": True,
            },
        )

    @staticmethod
    def build_aspc_id(asp_id: str, environment: str, subpanel_id: str | None = None) -> str:
        """Build the ASPC business key from the unique runtime configuration tuple."""
        asp = validate_identifier(asp_id, label="asp_id")
        subpanel = validate_identifier(subpanel_id or SUBPANEL_BASE_ID, label="subpanel_id")
        env = normalize_environment(environment)
        return f"{asp}_{subpanel}_{env}"

    @staticmethod
    def _normalize_aspc_id(aspc_id: str | None) -> str | None:
        """Normalize aspc id.

        Args:
                aspc_id: Aspc id.

        Returns:
                The  normalize aspc id result.
        """
        if aspc_id is None:
            return None
        normalized = str(aspc_id).strip()
        return normalized or None

    def _aspc_lookup_query(self, aspc_id: str) -> dict:
        """Aspc lookup query.

        Args:
                aspc_id: Aspc id.

        Returns:
                The  aspc lookup query result.
        """
        normalized = self._normalize_aspc_id(aspc_id)
        return {"aspc_id": normalized}

    def ensure_aspc_id(self, data: dict) -> dict:
        """Ensure an ASP-config payload carries a normalized business key."""
        if not isinstance(data, dict):
            return data
        normalized = self._normalize_aspc_id(data.get("aspc_id"))
        if not normalized and data.get("asp_id") and data.get("environment"):
            normalized = self.build_aspc_id(
                str(data.get("asp_id")),
                str(data.get("environment")),
                str(data.get("subpanel_id") or SUBPANEL_BASE_ID),
            )
        if normalized:
            data["aspc_id"] = normalized
            data["subpanel_id"] = str(data.get("subpanel_id") or SUBPANEL_BASE_ID).strip()
            return data
        raise ValueError("asp_configs.aspc_id is required in strict business-key mode")

    def count_aspcs(self, is_active: bool | None = None) -> int:
        """
        Count ASPCs with an optional active-status filter.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return int(self.get_collection().count_documents(query))

    def get_all_aspc(self) -> cursor.Cursor:
        """
        Retrieves all assay configuration documents from the collection.

        Returns:
            pymongo.cursor.Cursor: A cursor to iterate over all assay configuration documents.
        """
        return self.get_collection().find({})

    def search_aspcs(
        self, *, q: str = "", page: int = 1, per_page: int = 30, is_active: bool | None = True
    ) -> tuple[list[dict], int]:
        """Search assay configs directly in MongoDB and return paged results."""
        query: dict = {}
        if is_active is not None:
            query["is_active"] = is_active
        normalized_q = str(q or "").strip()
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$or"] = [
                {"aspc_id": {"$regex": pattern, "$options": "i"}},
                {"asp_id": {"$regex": pattern, "$options": "i"}},
                {"subpanel_id": {"$regex": pattern, "$options": "i"}},
                {"environment": {"$regex": pattern, "$options": "i"}},
                {"assay_type": {"$regex": pattern, "$options": "i"}},
                {"category": {"$regex": pattern, "$options": "i"}},
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        total = int(col.count_documents(query))
        docs = list(
            col.find(query)
            .sort([("asp_id", 1), ("subpanel_id", 1), ("environment", 1)])
            .skip(skip)
            .limit(per_page)
        )
        return docs, total

    def get_aspc(
        self, assay: str, profile: str = "production", subpanel_id: str | None = None
    ) -> dict | None:
        """
        Retrieves a specific assay configuration document by its ID.

        Args:
            assay (str): The unique identifier of the assay configuration.
            profile (str): The environment profile associated with the assay configuration (default is "production").

        Returns:
            dict | None: The assay configuration document if found, otherwise None.
        """
        aspc_id = self.build_aspc_id(assay, profile, subpanel_id)
        return self.get_collection().find_one({"aspc_id": aspc_id, "is_active": True})

    def get_aspc_with_id(self, aspc_id: str) -> dict | None:
        """
        Retrieves a specific assay configuration document by its ID.

        Args:
            aspc_id (str): The unique identifier of the assay configuration. Usually formatted as "assay:profile".

        Returns:
            dict | None: The assay configuration document if found, otherwise None.
        """
        return self.get_collection().find_one(
            {**self._aspc_lookup_query(aspc_id), "is_active": True}
        )

    def get_aspc_no_meta(
        self, assay_id: str, profile: str = "production", subpanel_id: str | None = None
    ) -> dict | None:
        """
        Retrieves a specific assay configuration document by its ID, ensuring it is active.

        This method filters the assay configuration document by its unique identifier (`_id`)
        and checks that the `is_active` field is set to `True`. Additionally, it excludes
        metadata fields such as `updated_on`, `updated_by`, `created_on`, and `created_by`
        from the result.

        Args:
            assay_id (str): The unique identifier of the assay configuration.
            profile (str): The profile name to filter the assay configuration.

        Returns:
            dict: The filtered assay configuration document if found, otherwise `None`.
        """
        projection = {
            "updated_on": 0,
            "updated_by": 0,
            "created_on": 0,
            "created_by": 0,
        }
        normalized_subpanel = str(subpanel_id or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID
        lookup_subpanels = [normalized_subpanel]
        if normalized_subpanel != SUBPANEL_BASE_ID:
            lookup_subpanels.append(SUBPANEL_BASE_ID)
        for lookup_subpanel in lookup_subpanels:
            aspc_id = self.build_aspc_id(assay_id, profile, lookup_subpanel)
            doc = self.get_collection().find_one(
                {"$and": [self._aspc_lookup_query(aspc_id), {"is_active": True}]},
                projection,
            )
            if doc:
                return doc
        return None

    def get_active_aspcs_for_asp(self, asp_id: str, environment: str = "production") -> list[dict]:
        """Return active assay configurations for one ASP and environment."""
        assay_id = str(asp_id or "").strip()
        env = normalize_environment(environment)
        if not assay_id:
            return []
        return list(
            self.get_collection()
            .find({"asp_id": assay_id, "environment": env, "is_active": True})
            .sort([("catalog.display_order", 1), ("subpanel_id", 1), ("aspc_id", 1)])
        )

    def update_aspc(self, aspc_id: str, data: dict) -> OperationResult:
        """
        Updates an existing assay configuration document with new data.

        Args:
            aspc_id (str): The unique identifier of the assay configuration to update. (assay:profile format)
            data (dict): A dictionary containing the fields to update and their new values.

        Returns:
            Structured write result for the update.
        """
        result = self.get_collection().update_one(
            {**self._aspc_lookup_query(aspc_id), "is_active": True},
            {"$set": self.ensure_aspc_id(data)},
        )
        operation = OperationResult.from_update(result)
        invalidate_dashboard_summary_cache(self.adapter)
        return operation

    def rotate_aspc(
        self, aspc_id: str, replacement: dict, retire_fields: dict | None = None
    ) -> OperationResult:
        """Retire the active ASPC document and insert a new active version."""
        replacement_doc = self.ensure_aspc_id(dict(replacement))
        replacement_doc.pop("_id", None)
        replacement_doc["is_active"] = True
        retire_payload = {"is_active": False, **(retire_fields or {})}
        query = {**self._aspc_lookup_query(aspc_id), "is_active": True}
        update_result = self.get_collection().update_one(query, {"$set": retire_payload})
        if update_result.matched_count == 0:
            return OperationResult.from_update(update_result)
        try:
            insert_result = self.get_collection().insert_one(replacement_doc)
        except Exception:
            self.get_collection().update_one(
                {**self._aspc_lookup_query(aspc_id), "is_active": False},
                {"$set": {"is_active": True}},
            )
            raise
        invalidate_dashboard_summary_cache(self.adapter)
        return OperationResult.from_insert_one(insert_result)

    def create_assay_config(self, data: dict) -> OperationResult:
        """
        Inserts a new assay configuration document into the collection.

        Args:
            data (dict): A dictionary containing the assay configuration fields and their values.

        Returns:
            Structured write result for the insert.
        """
        result = self.get_collection().insert_one(self.ensure_aspc_id(dict(data)))
        operation = OperationResult.from_insert_one(result)
        invalidate_dashboard_summary_cache(self.adapter)
        return operation

    def delete_assay_config(self, assay_id: str) -> OperationResult:
        """
        Deletes an assay configuration document by its ID.

        Args:
            assay_id (str): The unique identifier of the assay configuration to delete.

        Returns:
            Structured write result for the delete.
        """
        result = self.get_collection().update_one(
            {**self._aspc_lookup_query(assay_id), "is_active": True},
            {"$set": {"is_active": False}},
        )
        operation = OperationResult.from_update(result)
        invalidate_dashboard_summary_cache(self.adapter)
        return operation

    def toggle_aspc_active(self, aspc_id: str, active_status: bool) -> OperationResult:
        """
        Toggles the active status of an assay configuration document by updating its 'is_active' field.

        Args:
            aspc_id (str): The unique identifier of the assay configuration to update.
            active_status (bool): The desired active status to set for the assay configuration.

        Returns:
            Structured write result for the update.
        """
        result = self.get_collection().update_one(
            self._aspc_lookup_query(aspc_id),
            {"$set": {"is_active": active_status}},
        )
        operation = OperationResult.from_update(result)
        invalidate_dashboard_summary_cache(self.adapter)
        return operation

    def get_all_assay_names(self, is_active: bool | None = None) -> dict:
        """
        Retrieves a distinct list of all assay names from the collection.

        Returns:
            dict: A dictionary containing all unique assay names.
        """
        if is_active is None:
            return self.get_collection().distinct("asp_id")
        else:
            return self.get_collection().find({"is_active": is_active}).distinct("asp_id")

    def get_available_assay_envs(
        self,
        assay_name: str,
        all_envs: list,
        subpanel_id: str | None = None,
    ) -> list:
        """
        Retrieves a list of available environments for a specific assay configuration.

        Args:
            assay_name (str): The base assay name (e.g., "Demo").
            all_envs (list): All supported environments (e.g., ["production", "development", "validation"]).

        Returns:
            list: A list of environments not yet used for this assay.
        """
        query = {
            "asp_id": assay_name,
            "subpanel_id": str(subpanel_id or SUBPANEL_BASE_ID).strip(),
        }
        assay_configs = self.get_collection().find(query, {"environment": 1})

        used_envs = set()
        for config in assay_configs:
            env = config.get("environment")
            if env:
                used_envs.add(env)

        return [env for env in all_envs if env not in used_envs]
