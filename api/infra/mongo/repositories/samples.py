"""
SampleRepository module for Coyote3
================================

This module defines the `SampleRepository` class used for accessing and managing
sample data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import re
from typing import Any

from bson.objectid import ObjectId
from pymongo import ReturnDocument

from api.infra.mongo.persistence import restore_object_ids
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repositories.sample_statistics import SampleStatisticsMixin
from api.infra.mongo.repository_utils import generate_sample_cache_key
from api.infra.mongo.transactions import run_transaction
from api.infra.samples_cache import invalidate_samples_cache, samples_cache_version
from coyote3.application.common.execution_context import current_username
from coyote3.application.common.record_attribution import attribute_record
from coyote3.contracts.operations import OperationResult
from coyote3.contracts.schemas.samples import SampleAspcResolutionDoc
from coyote3.domain.common.errors import api_error

SAMPLE_LIST_SORT_FIELDS: dict[str, str] = {
    "sample": "name",
    "case_id": "case_id",
    "case_clarity": "case.clarity_id",
    "control": "control_id",
    "control_clarity": "control.clarity_id",
    "environment": "environment",
    "asp_id": "asp_id",
    "diagnosis": "diagnosis_id",
    "pipeline": "pipeline",
    "analysis": "ingest_status",
    "added": "time_added",
    "latest_reported": "latest_report_on",
}


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class SampleRepository(SampleStatisticsMixin, BaseRepository):
    """
    SampleRepository is a class that provides an interface for interacting with the samples data in the MongoDB collection.

    This class extends the BaseRepository class and provides methods for performing CRUD operations, querying sample data,
    managing sample settings, handling comments, and generating statistics. It is designed to facilitate efficient
    interaction with sample documents, including support for caching, filtering, and report management.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.samples_collection)

    def ensure_indexes(self) -> None:
        """
        Create indexes used by dashboard and sample list/read paths.
        """
        col = self.get_collection()
        col.create_index([("asp_id", 1)], name="asp_id_1", background=True)
        col.create_index(
            [("name", 1)],
            name="name_1",
            unique=True,
            background=True,
            partialFilterExpression={"name": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("environment", 1)], name="environment_1", background=True)
        col.create_index([("reported", 1)], name="reported_1", background=True)
        col.create_index([("time_added", -1)], name="time_added_-1", background=True)
        col.create_index(
            [("reported", 1), ("latest_report_on", -1)],
            name="reported_1_latest_report_on_-1",
            background=True,
        )
        col.create_index([("paired", 1)], name="paired_1", background=True)
        col.create_index(
            [("asp_id", 1), ("environment", 1), ("reported", 1)],
            name="asp_id_1_environment_1_reported_1",
            background=True,
        )
        col.create_index(
            [("asp_id", 1), ("environment", 1), ("time_added", -1)],
            name="asp_id_1_environment_1_time_added_-1",
            background=True,
        )
        col.create_index(
            [
                ("ingest_status", 1),
                ("asp_category", 1),
                ("asp_id", 1),
                ("environment", 1),
            ],
            name="ingest_status_1_asp_category_1_asp_id_1_environment_1",
            background=True,
        )

    @staticmethod
    def _build_samples_query(
        *,
        user_assays: list | None,
        user_envs: list | None,
        report: bool,
        search_str: str,
        time_limit=None,
        added_from=None,
        added_until=None,
    ) -> dict[str, Any]:
        """Build the shared sample-list filter used for rows and totals."""
        query: dict[str, Any] = {"ingest_status": "ready"}
        if user_assays is not None:
            query["asp_id"] = {"$in": user_assays}
        if user_envs is not None:
            query["environment"] = {"$in": user_envs}

        clauses: list[dict[str, Any]] = []
        if report:
            query["reported"] = True
            if time_limit:
                query["latest_report_on"] = {"$gt": time_limit}
        else:
            clauses.append(
                {
                    "$or": [
                        {"reported": {"$exists": False}},
                        {"reported": False},
                    ]
                }
            )

        normalized_search = (search_str or "").strip()
        if normalized_search:
            literal_match = {"$regex": re.escape(normalized_search), "$options": "i"}
            clauses.append(
                {
                    "$or": [
                        {field: literal_match}
                        for field in (
                            "name",
                            "case_id",
                            "control_id",
                            "case.id",
                            "case.clarity_id",
                            "control.id",
                            "control.clarity_id",
                        )
                    ]
                }
            )

        if clauses:
            query["$and"] = clauses

        if added_from is not None or added_until is not None:
            added_range: dict[str, Any] = {}
            if added_from is not None:
                added_range["$gte"] = added_from
            if added_until is not None:
                added_range["$lt"] = added_until
            query["time_added"] = added_range

        return query

    def _query_samples(
        self,
        user_assays: list | None,
        user_envs: list | None,
        report: bool,
        search_str: str,
        limit=None,
        offset: int = 0,
        time_limit=None,
        added_from=None,
        added_until=None,
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
            - If `report` is True, filters samples with reported = True.
            - If `report` is False, filters samples with reported = False or not present.
            - If `search_str` is provided, filters samples by name using regex.
        """
        query = self._build_samples_query(
            user_assays=user_assays,
            user_envs=user_envs,
            report=report,
            search_str=search_str,
            time_limit=time_limit,
            added_from=added_from,
            added_until=added_until,
        )

        app_obj = self.adapter.app
        getattr(app_obj, "home_logger", app_obj.logger).debug(f"Sample query: {query}")

        cursor = self.get_collection().find(query).sort("time_added", -1)
        if offset and offset > 0:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_samples_page(
        self,
        *,
        user_assays: list | None,
        user_envs: list | None,
        status: str,
        report: bool,
        search_str: str,
        sort: str,
        limit: int,
        offset: int = 0,
        time_limit=None,
        added_from=None,
        added_until=None,
    ) -> dict[str, Any]:
        """Return one sample page and its exact filtered total in one query."""
        query = self._build_samples_query(
            user_assays=user_assays,
            user_envs=user_envs,
            report=report,
            search_str=search_str,
            time_limit=time_limit,
            added_from=added_from,
            added_until=added_until,
        )
        app_obj = self.adapter.app
        getattr(app_obj, "home_logger", app_obj.logger).debug(
            "Sample page query (%s): %s", status, query
        )
        sort_spec: dict[str, int] = {}
        for item in (sort or "").split(","):
            field_id, _, direction = item.partition(":")
            mongo_field = SAMPLE_LIST_SORT_FIELDS.get(field_id.strip())
            if mongo_field:
                sort_spec[mongo_field] = -1 if direction.strip().lower() == "desc" else 1
        if not sort_spec:
            sort_spec["latest_report_on" if report else "time_added"] = -1
        if "_id" not in sort_spec:
            sort_spec["_id"] = -1

        result = list(
            self.get_collection().aggregate(
                [
                    {"$match": query},
                    {"$sort": sort_spec},
                    {
                        "$facet": {
                            "items": [{"$skip": max(0, offset)}, {"$limit": limit}],
                            "count": [{"$count": "total"}],
                        }
                    },
                ]
            )
        )
        page = result[0] if result else {}
        count_rows = page.get("count") or []
        total = int(count_rows[0].get("total") or 0) if count_rows else 0
        return {"items": list(page.get("items") or []), "total": total}

    def get_samples(
        self,
        user_assays: list | None,
        user_envs: list | None = None,
        status: str = "live",
        report: bool = False,
        search_str: str = "",
        limit: int = None,
        offset: int = 0,
        time_limit=None,
        added_from=None,
        added_until=None,
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
        app_obj = self.adapter.app
        cache_timeout = app_obj.config.get("CACHE_DEFAULT_TIMEOUT", 0)
        cache = getattr(app_obj, "cache", None)

        cache_key = generate_sample_cache_key(
            cache_version=samples_cache_version(app_obj),
            user_assays=user_assays,
            user_envs=user_envs,
            status=status,
            report=report,
            search_str=search_str,
            limit=limit,
            offset=offset,
            time_limit=time_limit,
            added_from=added_from,
            added_until=added_until,
            cache_timeout=cache_timeout,
            reload=reload,
        )

        if use_cache and cache is not None:
            try:
                samples = cache.get(cache_key)
            except Exception as exc:
                app_obj.logger.warning(
                    "[SAMPLES CACHE ERROR] failed to read cache key %s: %s. Falling back to DB.",
                    cache_key,
                    exc,
                )
                samples = None

            if samples and not reload:
                app_obj.logger.debug("[SAMPLES CACHE HIT] %s", cache_key)
                return samples
            elif samples and reload:
                app_obj.logger.debug(
                    "[SAMPLES CACHE HIT] %s - but reloading from DB since reload is set to True.",
                    cache_key,
                )
            else:
                app_obj.logger.debug("[SAMPLES CACHE MISS] %s - fetching from DB.", cache_key)

        # If no cache or use_cache=False, or cache miss
        samples = self._query_samples(
            user_assays=user_assays,
            user_envs=user_envs,
            report=report,
            search_str=search_str,
            limit=limit,
            offset=offset,
            time_limit=time_limit,
            added_from=added_from,
            added_until=added_until,
        )

        if use_cache and cache is not None:
            try:
                cache.set(cache_key, samples, timeout=cache_timeout)
                app_obj.logger.debug(
                    "[SAMPLES CACHE SET] %s (timeout=%ss)", cache_key, cache_timeout
                )
            except Exception as exc:
                app_obj.logger.warning(
                    "[SAMPLES CACHE ERROR] failed to set cache key %s: %s. Continuing without cache.",
                    cache_key,
                    exc,
                )

        return samples

    def count_ready_samples_by_asp(
        self,
        *,
        user_assays: list[str] | None,
        user_envs: list[str] | None,
    ) -> dict[str, int]:
        """Return ready sample counts grouped by assay panel ID."""
        query: dict[str, Any] = {"ingest_status": "ready"}
        if user_assays is not None:
            query["asp_id"] = {"$in": user_assays}
        if user_envs is not None:
            query["environment"] = {"$in": user_envs}

        rows = self.get_collection().aggregate(
            [
                {"$match": query},
                {"$group": {"_id": "$asp_id", "count": {"$sum": 1}}},
            ]
        )
        return {str(row.get("_id")): int(row.get("count") or 0) for row in rows if row.get("_id")}

    def get_gene_cohort_samples(
        self,
        *,
        asp_ids: list[str] | None,
        environments: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Return ready samples with only fields needed for gene cohort denominators."""
        query: dict[str, Any] = {"ingest_status": "ready"}
        if asp_ids is not None:
            query["asp_id"] = {"$in": asp_ids}
        if environments is not None:
            query["environment"] = {"$in": environments}
        projection = {
            "name": 1,
            "asp_id": 1,
            "diagnosis_id": 1,
            "environment": 1,
            "sex": 1,
            "filters": 1,
            "analysis_intents": 1,
            "asp_category": 1,
            "reported": 1,
            "latest_report_id": 1,
            "files": 1,
            "current_aspc_id": 1,
            "version": 1,
        }
        return list(self.get_collection().find(query, projection))

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

    def get_notification_sample(self, sample_id: str) -> dict | None:
        """Read report notification context without treating database errors as missing samples.

        Args:
            sample_id: Committed report's sample ObjectId as text.

        Returns:
            Minimal identity/scope fields with the active ASP's current group; None
            for a deleted or invalid identity. A missing/retired ASP yields no group,
            so clinical notification addressing does not trust stale sample metadata.

        Raises:
            PyMongoError: MongoDB is unavailable; notification delivery must retry.
        """
        if not ObjectId.is_valid(sample_id):
            return None
        sample = self.get_collection().find_one(
            {"_id": ObjectId(sample_id)},
            {"name": 1, "asp_id": 1, "environment": 1},
        )
        if sample is not None:
            assay = self.adapter.asp_collection.find_one(
                {"asp_id": sample.get("asp_id"), "is_active": True}, {"asp_group": 1}
            )
            sample["asp_group"] = (assay or {}).get("asp_group")
        return sample

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
            self.adapter.app.logger.error("Error retrieving sample by id %s: %s", id, e)
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
                "asp_id": 1,
                "diagnosis_id": 1,
                "environment": 1,
                "case_id": 1,
                "control_id": 1,
            },
        )

    def reset_sample_settings(
        self,
        sample_id: str,
        default_filters: dict,
        *,
        aspc: dict | None = None,
        analysis_intents: list[str] | None = None,
        expected_version: int | None = None,
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
        default_filters = dict(default_filters or {})
        default_filters.pop("_id", None)
        default_filters.pop("id_", None)
        self.update_sample_filters(
            sample_id,
            default_filters,
            aspc=aspc,
            analysis_intents=analysis_intents,
            expected_version=expected_version,
            settings_reason="Reset to applied configuration defaults",
        )

    def update_sample_filters(
        self,
        sample_id: str,
        filters: dict,
        *,
        aspc: dict | None = None,
        analysis_intents: list[str] | None = None,
        expected_version: int | None = None,
        settings_reason: str | None = None,
    ) -> None:
        """Commit sample settings and their before/after audit receipt atomically.

        Args:
            sample_id: Sample ObjectId represented as a string.
            filters: Complete validated effective filter settings.
            aspc: Exact configuration revision being applied, or None to retain it.
            analysis_intents: Replacement intents, or None to retain existing intents.
            expected_version: Optimistic concurrency precondition, when supplied.
            settings_reason: Operator explanation recorded in the audit event.

        Raises:
            AppError: The sample is absent or its operation version changed.
        """
        update = {"filters": filters, "updated_by": current_username("") or None}
        if isinstance(aspc, dict):
            update["current_aspc_id"] = aspc.get("_id")
            update["current_aspc_name"] = aspc.get("display_name") or aspc["aspc_id"]
            if isinstance(aspc.get("aspc_resolution"), dict):
                update["aspc_resolution"] = SampleAspcResolutionDoc.from_resolution(
                    aspc["aspc_resolution"]
                ).model_dump()
        if analysis_intents is not None:
            update["analysis_intents"] = analysis_intents
        selector = {"_id": ObjectId(sample_id)}
        if expected_version is not None:
            selector["version"] = expected_version

        def persist(session):
            """Commit settings and their application audit together under the sample version guard."""
            previous = self.get_collection().find_one_and_update(
                selector,
                {"$set": update, "$inc": {"version": 1}},
                return_document=ReturnDocument.BEFORE,
                session=session,
            )
            if previous is None:
                raise api_error(409, "Sample settings changed. Reload the sample before saving.")
            enqueue_audit(
                self.get_collection().database,
                session,
                event_type="sample.configuration_applied" if aspc else "sample.filters_updated",
                resource_type="sample",
                resource_id=sample_id,
                actor=current_username(),
                metadata={
                    "reason": settings_reason,
                    "previous_version": previous["version"],
                    "new_version": previous["version"] + 1,
                    "before": {key: previous.get(key) for key in update},
                    "after": update,
                },
            )

        run_transaction(self.adapter.client, persist)
        invalidate_samples_cache(self.adapter)
        self.invalidate_dashboard_metrics()

    def update_sample(self, sample_id: ObjectId, sample_doc: dict) -> OperationResult:
        """
        Update sample document
        """
        expected_version = sample_doc["version"]
        previous = self.get_collection().find_one({"_id": sample_id, "version": expected_version})
        if previous is None:
            raise api_error(409, "Sample changed. Reload the sample before saving metadata.")
        replacement = restore_object_ids(
            attribute_record(
                {**sample_doc, "version": expected_version + 1},
                actor=current_username("") or sample_doc.get("updated_by"),
                previous=previous,
            )
        )
        result = self.get_collection().replace_one(
            {"_id": sample_id, "version": expected_version}, replacement
        )
        if not result.matched_count:
            raise api_error(409, "Sample changed. Reload the sample before saving metadata.")
        invalidate_samples_cache(self.adapter)
        self.invalidate_dashboard_metrics()
        return OperationResult.from_update(result)

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
        sample = self.get_sample(sample_id)
        self.adapter.sample_comment_repository.add_sample_comment(
            sample=sample,
            comment_doc=comment_doc,
        )

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
        self.adapter.sample_comment_repository.set_hidden(
            sample_oid=id,
            comment_id=comment_id,
            hidden=True,
        )

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
        self.adapter.sample_comment_repository.set_hidden(
            sample_oid=id,
            comment_id=comment_id,
            hidden=False,
        )

    def hidden_sample_comments(self, id: str) -> bool:
        """
        Check if a sample has hidden comments.

        Returns:
            bool: True if the sample has hidden comments, otherwise False.
        """
        return self.adapter.sample_comment_repository.hidden_sample_comments(id)

    def get_latest_sample_comment(self, sample_id: str) -> dict | None:
        """
        Retrieve the latest comment for a specific sample.

        This method fetches the most recent comment added to the specified sample.

        Args:
            sample_id (str): The unique identifier of the sample.
        Returns:
            dict | None: The latest comment document if found, otherwise None.
        """
        return self.adapter.sample_comment_repository.get_latest_sample_comment(sample_id)

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
            query = {"asp_id": {"$in": assays}}

        if len(search_str) > 0:
            query["name"] = {"$regex": re.escape(search_str)}

        if limit:
            samples = self.get_collection().find(query).sort("time_added", -1).limit(limit)
        else:
            samples = self.get_collection().find(query).sort("time_added", -1)

        return samples

    def search_samples_for_admin(
        self,
        *,
        asp_ids: list[str] | None = None,
        environments: list[str] | None = None,
        diagnosis_id: str | None = None,
        search_str: str = "",
        page: int = 1,
        per_page: int = 30,
        ready_only: bool = True,
    ) -> tuple[list[dict], int]:
        """Search samples in MongoDB for admin listings with pagination."""
        query: dict[str, Any] = {"ingest_status": "ready"} if ready_only else {}
        if asp_ids is not None:
            query["asp_id"] = {"$in": asp_ids}
        if environments is not None:
            query["environment"] = {"$in": environments}
        if diagnosis_id:
            query["diagnosis_id"] = (
                {"$in": ["base", None]} if diagnosis_id == "base" else diagnosis_id
            )
        normalized_q = str(search_str or "").strip()
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$or"] = [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"case_id": {"$regex": pattern, "$options": "i"}},
                {"control_id": {"$regex": pattern, "$options": "i"}},
                {"asp_id": {"$regex": pattern, "$options": "i"}},
                {"diagnosis_id": {"$regex": pattern, "$options": "i"}},
                {"environment": {"$regex": pattern, "$options": "i"}},
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        total = int(col.count_documents(query))
        docs = list(col.find(query).sort("time_added", -1).skip(skip).limit(per_page))
        return docs, total

    def delete_sample(self, sample_oid: str) -> OperationResult:
        """
        Delete a sample from the database.

        Args:
            sample_oid (str): The unique identifier (ObjectId) of the sample to delete.

        Returns:
            Structured write result for the delete.
        """
        result = self.get_collection().delete_one({"_id": ObjectId(sample_oid)})
        invalidate_samples_cache(self.adapter)
        operation = OperationResult.from_delete(result)
        self.invalidate_dashboard_metrics()
        return operation

    def save_report(
        self,
        sample_id: str,
        report_num: int,
        report_id: str,
        filepath: str,
        pdf_filepath: str | None = None,
        rule_provenance: dict | None = None,
        snapshot_rows: list[dict] | None = None,
        created_by: str | None = None,
        prepared_sample: dict | None = None,
        resolution_snapshot: dict | None = None,
        artifacts: list[dict] | None = None,
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
        sample = prepared_sample if prepared_sample is not None else self.get_sample(sample_id)
        if not sample:
            return None
        return self.adapter.report_repository.save_report(
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            filepath=filepath,
            pdf_filepath=pdf_filepath,
            rule_provenance=rule_provenance,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
            resolution_snapshot=resolution_snapshot,
            artifacts=artifacts,
        )

    def complete_report_artifacts(self, report_oid: Any) -> bool:
        """Mark a committed report's checksum-verified files ready."""
        return self.adapter.report_repository.complete_artifacts(report_oid)

    def get_report(self, sample_id: str, report_id: str) -> dict | None:
        """
        Retrieve a specific report from the `reports` array of a sample document.

        Args:
            sample_id (str): The unique identifier of the sample.
            report_id (str): The unique identifier of the report to retrieve.

        Returns:
            dict | None: The report document if found, otherwise None.
        """
        return self.adapter.report_repository.get_report(sample_id, report_id)
