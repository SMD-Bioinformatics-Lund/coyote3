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
SampleHandler module for Coyote3
================================

This module defines the `SampleHandler` class used for accessing and managing
sample data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
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
        user_assays: list,
        user_envs: list,
        report: bool,
        search_str: str,
        limit=None,
        time_limit=None,
    ):
        """
        Query samples based on user groups, report status, search string, and optional time limit.
        Args:
            user_assays (list): List of user group identifiers to filter samples.
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
        query: dict[str, dict[str, Any]] = {
            "assay": {"$in": user_assays},
            "profile": {"$in": user_envs},
        }

        if report:
            query["report_num"] = {"$gt": 0}
            if time_limit:
                query["reports"] = {"$elemMatch": {"time_created": {"$gt": time_limit}}}
        else:
            query["$or"] = [
                {"report_num": {"$exists": False}},
                {"report_num": 0},
            ]

        if search_str:
            query["name"] = {"$regex": search_str}

        app.home_logger.debug(f"Sample query: {query}")

        samples = list(self.get_collection().find(query).sort("time_added", -1))

        if limit:
            samples = samples[:limit]

        return samples

    def get_samples(
        self,
        user_assays: list,
        user_envs: list = ["production"],
        status: str = "live",
        report: bool = False,
        search_str: str = "",
        limit: int = None,
        time_limit=None,
        use_cache: bool = True,
        cache_timeout: int = 120,
        reload: bool = False,
    ) -> Any | list:
        """
        Retrieve sample records for the specified user groups, optionally using caching for performance.
        Args:
            user_assays (list): List of user group identifiers to filter samples.
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
            - Uses a cache key generated from user_assays, status, and search_str.
            - If caching is enabled and a cache hit occurs, returns cached samples.
            - On cache miss or if caching is disabled, queries the database and updates the cache.
        """
        cache_timeout = app.config.get("CACHE_DEFAULT_TIMEOUT", 0)

        cache_key = CommonUtility.generate_sample_cache_key(**locals())

        if use_cache:
            samples = app.cache.get(cache_key)
            if samples and not reload:
                app.logger.info(f"[SAMPLES CACHE HIT] {cache_key}")
                return samples
            elif samples and reload:
                app.logger.info(
                    f"[SAMPLES CACHE HIT] {cache_key} — but reloading from DB since reload is set to True."
                )
            else:
                app.logger.info(f"[SAMPLES CACHE MISS] {cache_key} — fetching from DB.")

        # If no cache or use_cache=False, or cache miss
        samples = self._query_samples(
            user_assays=user_assays,
            user_envs=user_envs,
            report=report,
            search_str=search_str,
            limit=limit,
            time_limit=time_limit,
        )

        if use_cache:
            app.cache.set(cache_key, samples, timeout=cache_timeout)
            app.logger.debug(f"[SAMPLES CACHE SET] {cache_key} (timeout={cache_timeout}s)")

        return samples

    def get_sample(self, sample_key: str) -> dict:
        """
        Retrieve a sample document by its name or id.

        This method fetches a sample document from the database using its name first,
        and if not found, tries by its id.

        Args:
            sample_key (str): The name or id of the sample to retrieve.

        Returns:
            dict: The sample document if found, otherwise empty dict.
        """
        sample = self.get_sample_by_name(sample_key)
        if not sample:
            sample = self.get_sample_by_id(sample_key)
        return sample if sample else {}

    def get_sample_by_name(self, name: str) -> dict | None:
        """
        Retrieve a sample document by its name.

        This method fetches a sample document from the database using its name.

        Args:
            name (str): The name of the sample to retrieve.

        Returns:
            dict | None: The sample document if found, otherwise None.
        """
        return self.get_collection().find_one({"name": name})

    def get_sample_by_id(self, id: str) -> dict | None:
        """
        Retrieve a sample document by its unique identifier.

        This method fetches a sample document from the database using its unique identifier.

        Args:
            id (str): The unique identifier (ObjectId) of the sample.

        Returns:
            dict | None: The sample document if found, otherwise None.
        """
        try:
            sample = self.get_collection().find_one({"_id": ObjectId(id)})
        except Exception as e:
            app.logger.error(f"Error retrieving sample by id {id}: {e}")
            sample = None
        return sample

    def get_sample_name(self, id: str) -> str | None:
        """
        Retrieve the name of a sample by its unique identifier.

        Args:
            id (str): The unique identifier (ObjectId) of the sample.

        Returns:
            str | None: The name of the sample if found, otherwise None.
        """
        sample = self.get_collection().find_one({"_id": ObjectId(id)})
        return sample.get("name") if sample else None

    def get_sample_by_oid(self, id: str) -> str | None:
        """
        Retrieve the name of a sample by its unique identifier.

        Args:
            id (ObjectId): The unique identifier (ObjectId) of the sample.

        Returns:
            dict | None: The sample doc if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": id})

    def get_samples_by_oids(self, sample_oids: list) -> Any:
        """
        Retrieve samples by their object IDs.

        Args:
          sample_oids (list): A list of ObjectId instances representing the sample IDs.

        Returns:
          Any: A cursor to the list of sample documents containing only the `name` field.
        """
        return self.get_collection().find(
            {"_id": {"$in": sample_oids}},
            {
                "name": 1,
                "assay": 1,
                "subpanel": 1,
                "profile": 1,
                "case_id": 1,
                "control_id": 1,
            },
        )

    def reset_sample_settings(self, sample_id: str, default_filters: dict) -> Any:
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

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        """
        Update the filters of a sample document in the database.

        This method updates the `filters` field of a sample document with the provided filters.

        Args:
            sample_id (str): The unique identifier (ObjectId) of the sample to update.
            filters (dict): A dictionary containing the new filter settings.

        Returns:
            None
        """
        self.get_collection().update_one(
            {"_id": ObjectId(sample_id)},
            {"$set": {"filters": filters}},
        )

    # TODO: Remove
    def update_temp_isgl(self, sample_id: str, temp_isgl: list) -> None:
        """
        Update the temporary isgl setting of a sample document in the database.

        This method updates the `temp_isgl` field of a sample document with the provided boolean value.

        Args:
            sample_id (str): The unique identifier (ObjectId) of the sample to update.
            temp_isgl (list): A list containing the new temporary isgl settings.

        Returns:
            None
        """
        self.get_collection().update_one(
            {"_id": ObjectId(sample_id)},
            {"$set": {"filters.temp_isgl": temp_isgl}},
        )

    def update_sample(self, sample_id: ObjectId, sample_doc: dict) -> None:
        """
        Update sample document
        """
        return self.get_collection().replace_one({"_id": sample_id}, sample_doc)

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

    def get_latest_sample_comment(self, sample_id: str) -> dict | None:
        """
        Retrieve the latest comment for a specific sample.

        This method fetches the most recent comment added to the specified sample.

        Args:
            sample_id (str): The unique identifier of the sample.
        Returns:
            dict | None: The latest comment document if found, otherwise None.
        """
        return self.get_latest_comment(sample_id)

    def get_all_sample_counts(self, report: bool | None = None) -> list:
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
            samples = self.get_collection().find().sort("time_added", -1).count()
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

    def user_sample_counts_by_assay(self, report: bool | None = None, assays: list = None) -> dict:
        """
        Retrieve the count of samples for each assay group.
        This method aggregates sample counts by assay groups, returning a dictionary
        where each key is an assay group and the value is the count of samples in that group.
        Args:
            assays (list, optional): A list of assay groups to filter the samples. If None, counts all samples.
        Returns:
            dict: A dictionary where each key is an assay group and the value is the count of samples in that group.
        """
        samples = []
        if report is None and assays is None:
            samples = self.get_collection().find().sort("time_added", -1).count()
        elif assays and report is None:
            samples = (
                self.get_collection()
                .find({"assay": {"$in": assays}})
                .sort("time_added", -1)
                .count()
            )

        pipeline = [
            {"$match": {"assay": {"$in": assays}}} if assays else {},
            {"$group": {"_id": "$assay", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "assay": "$_id", "count": 1}},
        ]
        if assays is None:
            pipeline = [
                {"$group": {"_id": "$assay", "count": {"$sum": 1}}},
                {"$project": {"_id": 0, "assay": "$_id", "count": 1}},
            ]
        result = list(self.get_collection().aggregate(pipeline))
        return {item["assay"]: item["count"] for item in result}

    def get_assay_specific_sample_stats(
        self, assays: list = None, profile: str = "production"
    ) -> dict:
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
        pipeline = []

        if assays:
            pipeline.append({"$match": {"assay": {"$in": assays}, "profile": profile}})

        pipeline.append(
            {
                "$group": {
                    "_id": {"assay": "$assay"},
                    "total": {"$sum": 1},
                    "analysed": {"$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 1, 0]}},
                    "pending": {"$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 0, 1]}},
                }
            }
        )

        result = list(self.get_collection().aggregate(pipeline))

        assay_group_stats = {}
        for doc in result:
            assay = doc["_id"]["assay"]
            assay_group_stats[assay] = {
                "total": doc.get("total", 0),
                "analysed": doc.get("analysed", 0),
                "pending": doc.get("pending", 0),
            }

        return assay_group_stats

    def get_all_samples(self, assays=None, limit=None, search_str="") -> Any:
        """
        Retrieve all samples from the database.

        This method fetches all sample records, optionally filtered by user assays and/or a search string.
        It can also limit the number of results returned.

        Args:
            assays (list, optional): A list of user group identifiers to filter the samples. Defaults to None.
            limit (int, optional): The maximum number of samples to return. If None, all matching samples are returned. Defaults to None.
            search_str (str, optional): A search string to filter samples by name using regex. Defaults to an empty string.

        Returns:
            Any: A cursor to the list of sample documents matching the query.
        """
        query = {}

        if assays:
            query = {"assay": {"$in": assays}}

        if len(search_str) > 0:
            query["name"] = {"$regex": search_str}

        if limit:
            samples = self.get_collection().find(query).sort("time_added", -1).limit(limit)
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
        self, sample_id: str, report_num: int, report_id: str, filepath: str
    ) -> bool | None:
        """
        Save a report to a sample document in the database.

        Args:
            sample_id (str): The unique identifier of the sample.
            report_num (int): The current running report number.
            report_id (str): The unique identifier of the report to save.
            filepath (str): The file path where the report is stored.

        Returns:
            bool | None: Returns the result of the database update operation.
        """
        report_oid = ObjectId()
        result = self.get_collection().update(
            {"name": sample_id},
            {
                "$push": {
                    "reports": {
                        "_id": report_oid,
                        "report_num": report_num,
                        "report_id": f"{report_id}",
                        "report_type": "html",
                        "report_name": f"{report_id}.html",
                        "filepath": filepath,
                        "author": current_user.username,
                        "time_created": CommonUtility.utc_now(),
                    }
                },
                "$set": {"report_num": report_num},
            },
        )
        if result.get("ok"):
            return report_oid
        return None

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

    def get_profile_counts(self) -> dict:
        """
        Retrieve the count of samples for each profile.

        This method aggregates sample counts by profile groups, returning a dictionary
        where each key is a profile and the value is the count of samples in that profile.

        Returns:
            dict: A dictionary where each key is a profile and the value is the count of samples in that profile.
        """
        pipeline = [
            {"$group": {"_id": "$profile", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "profile": "$_id", "count": 1}},
        ]
        result = list(self.get_collection().aggregate(pipeline))
        return {item["profile"]: item["count"] for item in result}

    def get_omics_counts(self) -> dict:
        """
        Retrieve the count of samples for each omics type.

        This method aggregates sample counts by omics types, returning a dictionary
        where each key is an omics type and the value is the count of samples in that omics type.

        Returns:
            dict: A dictionary where each key is an omics type and the value is the count of samples in that omics type.
        """
        pipeline = [
            {"$group": {"_id": "$omics_layer", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "omics_layer": "$_id", "count": 1}},
        ]
        result = list(self.get_collection().aggregate(pipeline))
        return {item["omics_layer"]: item["count"] for item in result}

    def get_sequencing_scope_counts(self) -> dict:
        """
        Retrieve the count of samples for each sequencing scope.

        This method aggregates sample counts by sequencing scopes, returning a dictionary
        where each key is a sequencing scope and the value is the count of samples in that scope.

        Returns:
            dict: A dictionary where each key is a sequencing scope and the value is the count of samples in that scope.
        """
        pipeline = [
            {"$group": {"_id": "$sequencing_scope", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "sequencing_scope": "$_id", "count": 1}},
        ]
        result = list(self.get_collection().aggregate(pipeline))
        return {item["sequencing_scope"]: item["count"] for item in result}

    def get_paired_sample_counts(self) -> dict:
        """
        Retrieve the count of paired, unpaired, and samples without a paired key.

        This method aggregates sample counts based on the `paired` field, returning a dictionary
        where each key is a boolean indicating whether the sample is paired (True) or unpaired (False),
        and None for samples without a paired key.

        Returns:
            dict: A dictionary with keys True, False, and None representing paired, unpaired, and missing paired status.
        """
        pipeline = [{"$group": {"_id": "$paired", "count": {"$sum": 1}}}]
        result = list(self.get_collection().aggregate(pipeline))
        # Ensure all three keys (True, False, None) are present in the result
        counts = {"paired": 0, "unpaired": 0, "unknown": 0}
        for item in result:
            if item["_id"] is True:
                counts["paired"] = item["count"]
            elif item["_id"] is False:
                counts["unpaired"] = item["count"]
            else:
                counts["unknown"] = item["count"]

        return counts
