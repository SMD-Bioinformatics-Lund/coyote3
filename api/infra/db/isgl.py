"""
ISGLHandler module for Coyote3
==========================================

This module defines the `ISGLHandler` class used for accessing and managing
gene panel data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import re
from typing import Any

from api.infra.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ISGLHandler(BaseHandler):
    """
    Coyote in silico gene asp database handler

    This class provides a comprehensive interface for managing gene panel data in the database.
    It supports operations such as retrieving, inserting, updating, and deleting gene panel records.
    Additionally, it includes methods for performing advanced queries, filtering, and calculations
    related to gene asp, assays, diagnoses, and associated metadata.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.insilico_genelist_collection)

    def ensure_indexes(self) -> None:
        """
        Create targeted indexes for ISGL visibility and assay/subpanel lookup paths.

        Avoids broad indexing to keep disk usage controlled.
        """
        col = self.get_collection()
        col.create_index(
            [("isgl_id", 1)],
            name="isgl_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"isgl_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index(
            [("is_active", 1), ("is_public", 1), ("adhoc", 1), ("created_on", -1)],
            name="active_public_adhoc_created_on",
            background=True,
        )
        col.create_index([("assays", 1)], name="assays_1", background=True)
        col.create_index([("diagnosis", 1)], name="diagnosis_1", background=True)
        col.create_index([("list_type", 1)], name="list_type_1", background=True)

    @staticmethod
    def _normalize_isgl_id(isgl_id: str | None) -> str | None:
        """Handle  normalize isgl id.

        Args:
                isgl_id: Isgl id.

        Returns:
                The  normalize isgl id result.
        """
        if isgl_id is None:
            return None
        normalized = str(isgl_id).strip()
        return normalized or None

    def _isgl_lookup_query(self, isgl_id: str) -> dict:
        """Handle  isgl lookup query.

        Args:
                isgl_id: Isgl id.

        Returns:
                The  isgl lookup query result.
        """
        normalized = self._normalize_isgl_id(isgl_id)
        return {"isgl_id": normalized}

    def ensure_isgl_id(self, data: dict) -> dict:
        """Handle ensure isgl id.

        Args:
            data (dict): Value for ``data``.

        Returns:
            dict: The function result.
        """
        if not isinstance(data, dict):
            return data
        normalized = self._normalize_isgl_id(data.get("isgl_id"))
        if normalized:
            data["isgl_id"] = normalized
            return data
        raise ValueError("insilico_genelists.isgl_id is required in strict business-key mode")

    def count_isgls(
        self,
        is_active: bool | None = None,
        is_public: bool | None = None,
        adhoc: bool | None = None,
    ) -> int:
        """
        Count ISGL documents with optional visibility/activity filters.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        if is_public is not None:
            query["is_public"] = is_public
        if adhoc is not None:
            query["adhoc"] = adhoc
        return int(self.get_collection().count_documents(query))

    def get_isgl(
        self, isgl_id: str, is_active: bool | None = None, is_public: bool | None = None
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
        query = self._isgl_lookup_query(isgl_id)
        if is_active is not None:
            query["is_active"] = is_active
        if is_public is not None:
            query["is_public"] = is_public
        return self.get_collection().find_one(query)

    def get_all_isgl(
        self,
        is_active: bool | None = None,
        is_public: bool | None = None,
        adhoc: bool | None = None,
    ) -> list:
        """
        Retrieve gene list documents matching optional filters.

        Args:
            is_active (bool | None): Filter by active status when provided.
            is_public (bool | None): Filter by public visibility when provided.
            adhoc (bool | None): Filter by adhoc flag when provided.

        Returns:
            list[dict]: Matching gene list documents with the `genes` field omitted,
                        sorted by `created_on` in descending order.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        if is_public is not None:
            query["is_public"] = is_public
        if adhoc is not None:
            query["adhoc"] = adhoc
        return list(self.get_collection().find(query, {"genes": 0}).sort([("created_on", -1)]))

    def search_isgls(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> tuple[list[dict], int]:
        """Search genelists directly in MongoDB and return paged results."""
        query: dict = {}
        normalized_q = str(q or "").strip()
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$or"] = [
                {"isgl_id": {"$regex": pattern, "$options": "i"}},
                {"name": {"$regex": pattern, "$options": "i"}},
                {"description": {"$regex": pattern, "$options": "i"}},
                {"list_type": {"$regex": pattern, "$options": "i"}},
                {"diagnosis": {"$regex": pattern, "$options": "i"}},
                {"assays": {"$regex": pattern, "$options": "i"}},
                {"assay_groups": {"$regex": pattern, "$options": "i"}},
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        total = int(col.count_documents(query))
        docs = list(
            col.find(query, {"genes": 0}).sort([("created_on", -1)]).skip(skip).limit(per_page)
        )
        return docs, total

    def get_dashboard_visibility_rollup(self) -> dict:
        """
        Aggregate ISGL visibility stats for dashboard payloads.
        """
        pipeline = [
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "public_total": {
                                    "$sum": {"$cond": [{"$eq": ["$is_public", True]}, 1, 0]}
                                },
                                "private_total": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$eq": [
                                                    "$is_private",
                                                    True,
                                                ]
                                            },
                                            1,
                                            {
                                                "$cond": [
                                                    {"$eq": ["$is_public", True]},
                                                    0,
                                                    1,
                                                ]
                                            },
                                        ]
                                    }
                                },
                                "adhoc_total": {
                                    "$sum": {"$cond": [{"$eq": ["$adhoc", True]}, 1, 0]}
                                },
                            }
                        },
                        {"$project": {"_id": 0}},
                    ],
                    "combos": [
                        {
                            "$project": {
                                "is_public": {"$eq": ["$is_public", True]},
                                "is_private": {
                                    "$cond": [
                                        {"$eq": ["$is_private", True]},
                                        True,
                                        {"$not": [{"$eq": ["$is_public", True]}]},
                                    ]
                                },
                                "is_adhoc": {"$eq": ["$adhoc", True]},
                            }
                        },
                        {
                            "$group": {
                                "_id": {
                                    "is_public": "$is_public",
                                    "is_private": "$is_private",
                                    "is_adhoc": "$is_adhoc",
                                },
                                "count": {"$sum": 1},
                            }
                        },
                    ],
                    "extra_visibility": [
                        {"$project": {"entries": {"$objectToArray": "$$ROOT"}}},
                        {"$unwind": "$entries"},
                        {"$match": {"entries.v": True}},
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$regexMatch": {"input": "$entries.k", "regex": "^is_"}},
                                        {
                                            "$not": [
                                                {
                                                    "$in": [
                                                        "$entries.k",
                                                        ["is_public", "is_private", "is_active"],
                                                    ]
                                                }
                                            ]
                                        },
                                    ]
                                }
                            }
                        },
                        {"$group": {"_id": "$entries.k", "count": {"$sum": 1}}},
                    ],
                }
            }
        ]
        doc = (list(self.get_collection().aggregate(pipeline, allowDiskUse=True)) or [{}])[0]
        totals = (doc.get("totals") or [{}])[0]
        counts_map: dict[tuple[bool, bool, bool], int] = {}
        for row in doc.get("combos", []) or []:
            combo = row.get("_id") or {}
            key = (
                bool(combo.get("is_public")),
                bool(combo.get("is_private")),
                bool(combo.get("is_adhoc")),
            )
            counts_map[key] = int(row.get("count", 0) or 0)

        extra_visibility_counts = {
            str(row.get("_id") or ""): int(row.get("count", 0) or 0)
            for row in (doc.get("extra_visibility") or [])
            if row.get("_id")
        }
        return {
            "public_total": int(totals.get("public_total", 0) or 0),
            "private_total": int(totals.get("private_total", 0) or 0),
            "adhoc_total": int(totals.get("adhoc_total", 0) or 0),
            "public_only": counts_map.get((True, False, False), 0),
            "private_only": counts_map.get((False, True, False), 0),
            "adhoc_only": counts_map.get((False, False, True), 0),
            "public_private": counts_map.get((True, True, False), 0),
            "public_adhoc": counts_map.get((True, False, True), 0),
            "private_adhoc": counts_map.get((False, True, True), 0),
            "public_private_adhoc": counts_map.get((True, True, True), 0),
            "overlap_total": (
                counts_map.get((True, True, False), 0)
                + counts_map.get((True, False, True), 0)
                + counts_map.get((False, True, True), 0)
                + counts_map.get((True, True, True), 0)
            ),
            "extra_visibility_counts": extra_visibility_counts,
        }

    def get_dashboard_assay_association_rollup(self) -> dict:
        """
        Aggregate ISGL association counts by ASP id for dashboard charts.
        """
        pipeline = [
            {"$match": {"assays": {"$exists": True, "$type": "array", "$ne": []}}},
            {"$unwind": "$assays"},
            {"$match": {"assays": {"$type": "string", "$ne": ""}}},
            {
                "$group": {
                    "_id": "$assays",
                    "isgl_total": {"$sum": 1},
                    "public_count": {"$sum": {"$cond": [{"$eq": ["$is_public", True]}, 1, 0]}},
                    "private_count": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": ["$is_private", True],
                                },
                                1,
                                {"$cond": [{"$eq": ["$is_public", True]}, 0, 1]},
                            ]
                        }
                    },
                    "adhoc_count": {"$sum": {"$cond": [{"$eq": ["$adhoc", True]}, 1, 0]}},
                }
            },
            {"$sort": {"isgl_total": -1, "_id": 1}},
        ]
        rows = list(self.get_collection().aggregate(pipeline, allowDiskUse=True))
        assay_ids = [str(row.get("_id")) for row in rows if row.get("_id")]
        asp_map = {
            str(doc.get("asp_id")): {
                "display_name": str(
                    doc.get("display_name") or doc.get("assay_name") or doc.get("asp_id") or ""
                ),
                "asp_group": str(doc.get("asp_group") or ""),
            }
            for doc in self.adapter.asp_collection.find(
                {"asp_id": {"$in": assay_ids}},
                {"_id": 0, "asp_id": 1, "display_name": 1, "assay_name": 1, "asp_group": 1},
            )
        }
        assay_rows = []
        for row in rows:
            assay_id = str(row.get("_id") or "")
            if not assay_id:
                continue
            meta = asp_map.get(assay_id, {})
            assay_rows.append(
                {
                    "assay_id": assay_id,
                    "display_name": meta.get("display_name") or assay_id,
                    "asp_group": meta.get("asp_group") or "",
                    "isgl_total": int(row.get("isgl_total", 0) or 0),
                    "public_count": int(row.get("public_count", 0) or 0),
                    "private_count": int(row.get("private_count", 0) or 0),
                    "adhoc_count": int(row.get("adhoc_count", 0) or 0),
                }
            )
        return {"assay_isgl_counts": assay_rows}

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
        return self.get_collection().insert_one(self.ensure_isgl_id(dict(data)))

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
            self._isgl_lookup_query(isgl_id), self.ensure_isgl_id(dict(updated_data))
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
        return self.get_collection().update_one(
            self._isgl_lookup_query(isgl_id),
            {"$set": {"is_active": active_status}},
        )

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
        return self.get_collection().delete_one(self._isgl_lookup_query(isgl_id))

    def get_subpanels_for_asp(
        self, asp_names: list[str], is_public: bool | None = None, adhoc: bool | None = None
    ) -> list[str]:
        """
        Retrieve unique diagnosis terms associated with a list of assay IDs.

        This method filters gene lists where any of the provided `asp_names` are included
        in the `assays` field (a list in the database) and collects all unique diagnosis terms.

        Args:
            asp_names (list[str]): A list of assay IDs to filter gene lists by.
            is_public (bool | None): Optional; if provided, filters gene lists by their public visibility.
            adhoc (bool | None): Optional; if provided, filters gene lists by their adhoc status

        Returns:
            list[str]: A sorted list of unique diagnosis terms associated with the assay IDs.
        """
        query = {"assays": {"$in": asp_names}}
        if is_public is not None:
            query["is_public"] = is_public
        if adhoc is not None:
            query["adhoc"] = adhoc
        cursor = self.get_collection().find(query)
        diagnoses = set()
        for doc in cursor:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_asp_subpanel_genes(self, asp_name: str, subpanel: str) -> list[str]:
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
        doc = self.get_collection().find_one({"assays": asp_name, "diagnosis": subpanel})
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
        return sorted(d for doc in self.get_collection().find({}) for d in doc.get("diagnosis", []))

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
        docs = self.get_collection().find({"diagnosis": {"$in": subpanels}}, {"genes": 1})
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
        query = self._isgl_lookup_query(isgl_id)
        query["is_active"] = is_active
        return self.get_collection().count_documents(query) > 0

    def get_isgl_by_asp(
        self,
        asp_name: str,
        is_active: bool | None = None,
        adhoc: bool | None = None,
        list_type: str | None = None,
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
            adhoc (bool, optional): The adhoc status of the gene lists to filter by.
                Defaults to None.

        Returns:
            list[dict]: A list of dictionaries representing the gene lists that match
            the query, with selected fields excluded.
        """
        query = {"assays": asp_name}
        if is_active is not None:
            query["is_active"] = is_active
        if adhoc is not None:
            query["adhoc"] = adhoc
        if list_type is not None:
            query["list_type"] = list_type
        projection = {
            "genes": 0,
            "created_on": 0,
            "created_by": 0,
            "version_history": 0,
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
        projection = {"isgl_id": 1}
        return [str(doc["isgl_id"]) for doc in self.get_collection().find(query, projection)]

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
        projection = {"isgl_id": 1, "is_active": 1, "displayname": 1, "genes": 1, "adhoc": 1}

        # Query the database for documents with matching IDs
        cursor = self.get_collection().find({"isgl_id": {"$in": isgl_ids}}, projection)

        # Format the result as a dictionary with IDs as keys
        return {doc.pop("isgl_id"): doc for doc in cursor}

    def get_public_isgl_genes_by_diagnosis(
        self, diagnosis: str, is_public: bool = True, is_active: bool = True
    ) -> list:
        """
        Retrieve genes from a public gene list document by diagnosis.

        This method queries the database collection for a document where the `diagnosis`
        field matches the provided `isgl_id` and the document is marked as public and active.
        It retrieves only the `genes` field and returns the list of gene symbols.

        Args:
            isgl_id (str): The diagnosis term to query.
            is_public (bool): Filter by public visibility. Defaults to True.
            is_active (bool): Filter by active status. Defaults to True.

        Returns:
            list: A list of gene symbols from the specified public gene list. If the
            gene list is not found or is not public, returns an empty list.
        """
        doc = self.get_collection().find_one(
            {"diagnosis": diagnosis, "is_public": is_public, "is_active": is_active}, {"genes": 1}
        )
        return doc.get("genes", []) if doc else []

    def is_isgl_adhoc(self, isgl_id: str) -> bool:
        """
        Check if a gene list is marked as adhoc.

        This method queries the database collection to determine if a gene list
        document with the specified `isgl_id` is marked as adhoc.

        Args:
            isgl_id (str): The unique identifier of the gene list to check.
        Returns:
            bool: True if the gene list is marked as adhoc, otherwise False.
        """
        doc = self.get_collection().find_one(self._isgl_lookup_query(isgl_id), {"adhoc": 1})
        return doc.get("adhoc", False) if doc else False

    def get_isgl_display_name(self, isgl_id: str) -> str | None:
        """
        Retrieve the display name of a gene list by its ID.

        This method queries the database collection for a gene list document
        with the specified `isgl_id` and retrieves its `displayname` field.

        Args:
            isgl_id (str): The unique identifier of the gene list.

        Returns:
            str | None: The display name of the gene list if found, otherwise None.
        """
        doc = self.get_collection().find_one(self._isgl_lookup_query(isgl_id), {"displayname": 1})
        return doc.get("displayname") if doc else None
