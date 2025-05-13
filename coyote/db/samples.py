# -*- coding: utf-8 -*-
"""
SampleHandler module for Coyote3
================================

This module defines the `SampleHandler` class used for accessing and managing
sample data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from bson.objectid import ObjectId
from coyote.db.base import BaseHandler
from datetime import datetime
from flask_login import current_user
from coyote.util.common_utility import CommonUtility
from flask import current_app as app
from typing import Any


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class SampleHandler(BaseHandler):
    """
    SampleHandler is a class that provides an interface for interacting with the samples data in the MongoDB collection.

    This class extends the BaseHandler class and provides methods for performing CRUD operations, querying sample data,
    managing sample settings, handling comments, and generating statistics. It is designed to facilitate efficient
    interaction with sample documents, including support for caching, filtering, and report management.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.samples_collection)

    def _query_samples(
        self,
        user_groups: list,
        report: bool,
        search_str: str,
        limit=None,
        time_limit=None,
    ):
        """
        Query samples based on user groups, report status, search string, and optional time limit.
        Args:
            user_groups (list): List of user group identifiers to filter samples.
            report (bool): Whether to include report-specific samples.
            search_str (str): Search string to filter samples.
            limit (int, optional): Maximum number of samples to return (default: None).
            time_limit (datetime, optional): Time constraint for filtering samples (default: None).
        Returns:
            list: List of sample records matching the specified criteria.
        Notes:
            - If `report` is True, filters samples with report_num > 0 and time_created > time_limit.
            - If `report` is False, filters samples with report_num = 0 or not present.
            - If `search_str` is provided, filters samples by name using regex.
        """
        query: dict[str, dict[str, Any]] = {"groups": {"$in": user_groups}}

        if report:
            query["report_num"] = {"$gt": 0}
            if time_limit:
                query["reports"] = {
                    "$elemMatch": {"time_created": {"$gt": time_limit}}
                }
        else:
            query["$or"] = [
                {"report_num": {"$exists": False}},
                {"report_num": 0},
            ]

        if search_str:
            query["name"] = {"$regex": search_str}

        app.home_logger.debug(f"Sample query: {query}")

        samples = list(
            self.get_collection().find(query).sort("time_added", -1)
        )

        if limit:
            samples = samples[:limit]

        return samples

    def get_samples(
        self,
        user_groups: list,
        status: str = "live",
        report: bool = False,
        search_str: str = "",
        limit: int = None,
        time_limit=None,
        use_cache: bool = True,
        cache_timeout: int = 120,
    ) -> Any | list:
        """
        Retrieve sample records for the specified user groups, optionally using caching for performance.
        Args:
            user_groups (list): List of user group identifiers to filter samples.
            status (str, optional): Status of the samples to retrieve (default: "live").
            report (bool, optional): Whether to include report-specific samples (default: False).
            search_str (str, optional): Search string to filter samples (default: "").
            limit (int, optional): Maximum number of samples to return (default: None, returns all).
            time_limit (optional): Time constraint for filtering samples (default: None).
            use_cache (bool, optional): Whether to use cache for retrieving samples (default: True).
            cache_timeout (int, optional): Cache timeout in seconds (default: 120).
        Returns:
            list: List of sample records matching the specified criteria.
        Notes:
            - Uses a cache key generated from user_groups, status, and search_str.
            - If caching is enabled and a cache hit occurs, returns cached samples.
            - On cache miss or if caching is disabled, queries the database and updates the cache.
        """
        cache_timeout = app.config.get("CACHE_TIMEOUT_SAMPLES", 120)

        cache_key = CommonUtility.generate_sample_cache_key(**locals())

        if use_cache:
            samples = app.cache.get(cache_key)
            if samples:
                app.logger.info(f"[SAMPLES CACHE HIT] {cache_key}")
                return samples
            else:
                app.logger.info(
                    f"[SAMPLES CACHE MISS] {cache_key} — fetching from DB."
                )

        # If no cache or use_cache=False, or cache miss
        samples = self._query_samples(
            user_groups=user_groups,
            report=report,
            search_str=search_str,
            limit=limit,
            time_limit=time_limit,
        )

        if use_cache:
            app.cache.set(cache_key, samples, timeout=cache_timeout)
            app.logger.debug(
                f"[SAMPLES CACHE SET] {cache_key} (timeout={cache_timeout}s)"
            )

        return samples

    def get_sample(self, name: str) -> dict | None:
        """
        Retrieve a sample document by its name.

        This method fetches a sample document from the database using its name.

        Args:
            name (str): The name of the sample to retrieve.

        Returns:
            dict | None: The sample document if found, otherwise None.
        """
        return self.get_collection().find_one({"name": name})

    def get_sample_with_id(self, id: str) -> dict | None:
        """
        Retrieve a sample document by its unique identifier.

        This method fetches a sample document from the database using its unique identifier.

        Args:
            id (str): The unique identifier (ObjectId) of the sample.

        Returns:
            dict | None: The sample document if found, otherwise None.
        """
        sample = self.get_collection().find_one({"_id": ObjectId(id)})
        return sample

    def get_sample_name(self, id: str) -> str | None:
        """
        get_sample_name(id: str) -> str | None

        Retrieve the name of a sample by its unique identifier.

        Args:
            id (str): The unique identifier (ObjectId) of the sample.

        Returns:
            str | None: The name of the sample if found, otherwise None.
        """
        sample = self.get_collection().find_one({"_id": ObjectId(id)})
        return sample.get("name") if sample else None

    def get_samples_by_oids(self, sample_oids: list) -> Any:
        """
        Retrieve samples by their object IDs.

        Args:
          sample_oids (list): A list of ObjectId instances representing the sample IDs.

        Returns:
          Any: A cursor to the list of sample documents containing only the `name` field.
        """
        return self.get_collection().find(
            {"_id": {"$in": sample_oids}}, {"name": 1}
        )

    def reset_sample_settings(
        self, sample_id: str, default_filters: dict
    ) -> Any:
        """
        Reset a sample to its default settings.

        This method updates the `filters` field of a sample document in the database
        to match the provided `default_filters` dictionary, excluding the
        `use_diagnosis_genelist` key if present.

        Args:
            sample_id (str): The unique identifier of the sample to reset.
            default_filters (dict): A dictionary containing the default filter settings.

        Returns:
            Any
        """
        # Remove unnecessary keys from default_filters
        default_filters.pop("use_diagnosis_genelist", None)

        self.get_collection().update(
            {"_id": ObjectId(sample_id)},
            {"$set": {"filters": default_filters}},
        )

    def update_sample_settings(self, sample_str: str, form) -> Any:
        """
        Update the `filters` field of a sample document based on data from a `FilterForm`.

        This method processes the form data, extracts relevant filter fields, and updates the sample's `filters` field in the database.

        Args:
            sample_str (str): The unique identifier (ObjectId) of the sample to update.
            form (FilterForm): The form containing filter data to apply.

        Returns:
            Any
        """
        form_data = form.data.copy()

        # Remove non-filter fields
        for key in ["csrf_token", "reset", "submit", "use_diagnosis_genelist"]:
            form_data.pop(key, None)

        # Extract Boolean categories
        vep_consequences = []
        genelists = []
        fusionlists = []
        fusioneffects = []
        fusioncallers = []
        cnveffects = []

        keys_to_remove = []
        keys_to_add = set()

        categories = {
            "genelist_": "genelists",
            "fusionlist_": "fusionlists",
            "fusioncaller_": "fusioncallers",
            "fusioneffect_": "fusioneffects",
            "cnveffect_": "cnveffects",
            "vep_": "vep_consequences",
        }

        for key, value in categories.items():
            if any(k.startswith(key) for k in form_data.keys()):
                keys_to_add.add(value)

        for field, value in form_data.items():
            if value is True:
                if field.startswith("genelist_"):
                    genelists.append(field.replace("genelist_", ""))
                elif field.startswith("fusionlist_"):
                    fusionlists.append(field.replace("fusionlist_", ""))
                elif field.startswith("fusioncaller_"):
                    fusioncallers.append(field.replace("fusioncaller_", ""))
                elif field.startswith("fusioneffect_"):
                    fusioneffects.append(field.replace("fusioneffect_", ""))
                elif field.startswith("cnveffect_"):
                    cnveffects.append(field.replace("cnveffect_", ""))
                elif field.startswith("vep_"):
                    vep_consequences.append(field.replace("vep_", ""))

                keys_to_remove.append(field)

        # Clean up processed boolean keys
        for k in keys_to_remove:
            form_data.pop(k, None)

        # Drop all remaining fields that are falsy (e.g. False, "", None)
        form_data = {k: v for k, v in form_data.items() if v}

        # Assemble final filters dict
        filters = {**form_data}

        if "vep_consequences" in keys_to_add:
            filters["vep_consequences"] = vep_consequences
        if "genelists" in keys_to_add:
            filters["genelists"] = genelists
        if "fusionlists" in keys_to_add:
            filters["fusionlists"] = fusionlists
        if "fusioneffects" in keys_to_add:
            filters["fusioneffects"] = fusioneffects
        if "fusion_callers" in keys_to_add:
            filters["fusion_callers"] = fusioncallers
        if "cnveffects" in keys_to_add:
            filters["cnveffects"] = cnveffects

        # Now update the sample doc
        self.get_collection().update_one(
            {"_id": ObjectId(sample_str)},
            {"$set": {"filters": filters}},
        )

    def add_sample_comment(self, sample_id: str, comment_doc: dict) -> None:
        """
        Add a comment to a sample.

        This method adds a new comment to the specified sample by calling the `update_comment` method.

        Args:
            sample_id (str): The unique identifier of the sample to which the comment will be added.
            comment_doc (dict): A dictionary containing the comment details, such as the text and metadata.

        Returns:
            None
        """
        self.update_comment(sample_id, comment_doc)

    def hide_sample_comment(self, id: str, comment_id: str) -> None:
        """
        Hide a sample comment.

        This method hides a specific comment for a given sample by marking it as hidden in the database.

        Args:
            id (str): The unique identifier of the sample.
            comment_id (str): The unique identifier of the comment to hide.

        Returns:
            None
        """
        self.hide_comment(id, comment_id)

    def unhide_sample_comment(self, id: str, comment_id: str) -> None:
        """
        Unhide a sample comment.

        This method unhides a previously hidden comment for a specific sample.

        Args:
            id (str): The unique identifier of the sample.
            comment_id (str): The unique identifier of the comment to unhide.

        Returns:
            None
        """
        self.unhide_comment(id, comment_id)

    def hidden_sample_comments(self, id: str) -> bool:
        """
        Check if a sample has hidden comments.

        Returns:
            bool: True if the sample has hidden comments, otherwise False.
        """
        return self.hidden_comments(id)

    def get_all_sample_counts(self, report=None) -> list:
        """
        Retrieve the total count of all samples in the database.

        This method fetches the total number of samples, optionally filtered by their report status:
        - If `report` is None, it retrieves the count of all samples.
        - If `report` is True, it retrieves the count of samples with reports.
        - If `report` is False, it retrieves the count of samples without reports.

        Returns:
            list: A list containing the total count of samples based on the specified criteria.
        """
        samples = []
        if report is None:
            samples = (
                self.get_collection().find().sort("time_added", -1).count()
            )
        elif report:
            samples = (
                self.get_collection()
                .find({"report_num": {"$gt": 0}})
                .sort("time_added", -1)
                .count()
            )
        elif not report:
            samples = (
                self.get_collection()
                .find(
                    {
                        "$or": [
                            {"report_num": 0},
                            {"report_num": None},
                            {"report_num": {"$exists": False}},
                        ]
                    }
                )
                .sort("time_added", -1)
                .count()
            )

        return samples

    def get_assay_specific_sample_stats(self) -> dict:
        """
        Retrieve assay-specific statistics.

        This method calculates statistics for each assay group, including:
        - Total number of samples.
        - Number of samples with reports.
        - Number of samples pending reports.

        Returns:
            dict: A dictionary where each key is an assay group, and the value is another dictionary containing:
                - 'total': Total number of samples in the group.
                - 'report': Number of samples with reports.
                - 'pending': Number of samples without reports.
        """
        pipeline = [
            {"$unwind": "$groups"},
            {
                "$group": {
                    "_id": "$groups",
                    "total": {"$sum": 1},
                    "report": {
                        "$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 1, 0]}
                    },
                    "pending": {
                        "$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 0, 1]}
                    },
                }
            },
            {
                "$group": {
                    "_id": None,
                    "stats": {
                        "$push": {
                            "group": "$_id",
                            "total": "$total",
                            "report": "$report",
                            "pending": "$pending",
                        }
                    },
                }
            },
            {"$project": {"_id": 0, "stats": 1}},
        ]

        result = list(self.get_collection().aggregate(pipeline))[0].get(
            "stats", []
        )
        assay_specific_stats = {
            stat.get("group"): {
                "total": stat.get("total", 0),
                "report": stat.get("report", 0),
                "pending": stat.get("pending", 0),
            }
            for stat in result
        }
        return assay_specific_stats

    def get_all_samples(self, groups=None, limit=None, search_str="") -> Any:
        """
        Retrieve all samples from the database.

        This method fetches all sample records, optionally filtered by user groups and/or a search string.
        It can also limit the number of results returned.

        Args:
            groups (list, optional): A list of user group identifiers to filter the samples. Defaults to None.
            limit (int, optional): The maximum number of samples to return. If None, all matching samples are returned. Defaults to None.
            search_str (str, optional): A search string to filter samples by name using regex. Defaults to an empty string.

        Returns:
            Any: A cursor to the list of sample documents matching the query.
        """
        query = {}

        if groups:
            query = {"groups": {"$in": groups}}

        if len(search_str) > 0:
            query["name"] = {"$regex": search_str}

        if limit:
            samples = (
                self.get_collection()
                .find(query)
                .sort("time_added", -1)
                .limit(limit)
            )
        else:
            samples = self.get_collection().find(query).sort("time_added", -1)

        return samples

    def delete_sample(self, sample_oid: str) -> None:
        """
        Delete a sample from the database.

        Args:
            sample_oid (str): The unique identifier (ObjectId) of the sample to delete.

        Returns:
            None
        """
        return self.get_collection().delete_one({"_id": ObjectId(sample_oid)})

    def save_report(
        self, sample_id: str, report_id: str, filepath: str
    ) -> bool | None:
        """
        Save a report to a sample document in the database.

        Args:
            sample_id (str): The unique identifier of the sample.
            report_id (str): The unique identifier of the report to save.
            filepath (str): The file path where the report is stored.

        Returns:
            bool | None: Returns the result of the database update operation.
        """
        report_num = int(report_id.split(".")[-1])
        return self.get_collection().update(
            {"name": sample_id},
            {
                "$push": {
                    "reports": {
                        "_id": ObjectId(),
                        "report_num": report_num,
                        "report_id": f"{report_id}",
                        "filepath": filepath,
                        "author": current_user.username,
                        "time_created": datetime.now(),
                    }
                },
                "$set": {"report_num": report_num},
            },
        )

    def get_report(self, sample_id: str, report_id: str) -> dict | None:
        """
        Retrieve a specific report from the `reports` array of a sample document.

        Args:
            sample_id (str): The unique identifier of the sample.
            report_id (str): The unique identifier of the report to retrieve.

        Returns:
            dict | None: The report document if found, otherwise None.
        """
        doc = self.get_collection().find_one(
            {"name": sample_id, "reports.report_id": report_id}, {"reports": 1}
        )

        if not doc:
            return None

        for report in doc.get("reports", []):
            if report.get("report_id") == report_id:
                return report

        return None
