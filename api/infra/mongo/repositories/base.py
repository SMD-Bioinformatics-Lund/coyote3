"""
CoverageRepository module for Coyote3
==================================

This module defines the `BaseRepository` class used for collection-scoped MongoDB
repository operations.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging
from types import SimpleNamespace
from typing import Any

import pymongo
from bson.objectid import ObjectId

from api.contracts.operations import OperationResult
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BaseRepository:
    """Base repository for collection-scoped MongoDB operations."""

    def __init__(self, adapter):
        """Initialize the repository with a Mongo adapter."""
        self.adapter = adapter
        self.app = getattr(
            adapter,
            "app",
            SimpleNamespace(logger=logging.getLogger("api.infra.mongo.repositories")),
        )

        self.repository_collection = None

    def set_collection(self, collection: pymongo.collection.Collection) -> None:
        """Bind the repository to a MongoDB collection."""
        self.repository_collection = collection

    def get_collection(self) -> pymongo.collection.Collection:
        """Return the MongoDB collection bound to this repository."""
        if self.repository_collection is not None:
            return self.repository_collection
        raise NotImplementedError("get_collection or set_collection must be implemented")

    def invalidate_dashboard_summary(self) -> None:
        """Invalidate dashboard metrics when this repository has a runtime adapter."""
        adapter = getattr(self, "adapter", None)
        if adapter is not None:
            invalidate_dashboard_summary_cache(adapter)

    def mark_false_positive(self, var_id: str, fp: bool) -> Any:
        """
        Mark / Unmark a variant as false positive.

        This method updates the `fp` field of a document in the collection to indicate
        whether the variant is a false positive.

        Args:
            var_id (str): The unique identifier of the variant or document.
            fp (bool): A boolean value indicating whether to mark the variant as false positive.

        Returns:
            Any: The result of the update operation.
        """
        return OperationResult.from_update(
            self.get_collection().update_one(
                {"_id": ObjectId(var_id)},
                {"$set": {"fp": fp}},
            )
        )

    def mark_false_positive_bulk(self, var_ids: list[str], fp: bool) -> Any:
        """
        Mark or unmark multiple variants as false positive in bulk.

        Args:
            var_ids (list[str]): List of variant document IDs (as strings).
            fp (bool): True to mark as false positive, False to unmark.

        Returns:
            Any: The result of the bulk write operation.
        """
        if not var_ids:
            return OperationResult.empty()

        object_ids: list[ObjectId] = []
        for vid in var_ids:
            try:
                object_ids.append(ObjectId(vid))
            except Exception:
                continue

        if not object_ids:
            return OperationResult.empty(requested_count=len(var_ids))

        try:
            return OperationResult.from_update(
                self.get_collection().update_many(
                    {"_id": {"$in": object_ids}},
                    {"$set": {"fp": fp}},
                ),
                requested_count=len(object_ids),
            )
        except Exception as exc:
            return OperationResult.failed(str(exc), requested_count=len(object_ids))

    def mark_interesting(self, var_id: str, interesting: bool) -> Any:
        """
        Mark a variant as interesting.

        This method updates the `interesting` field of a document in the collection
        to indicate whether the variant is considered interesting.

        Args:
            var_id (str): The unique identifier of the variant or document.
            interesting (bool): A boolean value indicating whether to mark the variant as interesting.

        Returns:
            Any: The result of the update operation.
        """
        return OperationResult.from_update(
            self.get_collection().update_one(
                {"_id": ObjectId(var_id)},
                {"$set": {"interesting": interesting}},
            )
        )

    def mark_irrelevant(self, var_id: str, irrelevant: bool) -> Any:
        """
        Mark / Unmark a variant as irrelevant.

        This method updates the `irrelevant` field of a document in the collection
        to indicate whether the variant is considered irrelevant.

        Args:
            var_id (str): The unique identifier of the variant or document.
            irrelevant (bool): A boolean value indicating whether to mark the variant as irrelevant.

        Returns:
            Any: The result of the update operation.
        """
        return OperationResult.from_update(
            self.get_collection().update_one(
                {"_id": ObjectId(var_id)},
                {"$set": {"irrelevant": irrelevant}},
            )
        )

    def mark_irrelevant_bulk(self, var_ids: list[str], irrelevant: bool) -> Any:
        """
        Mark or unmark multiple variants as irrelevant in bulk.

        Args:
            var_ids (list[str]): List of variant document IDs (as strings).
            irrelevant (bool): True to mark as irrelevant, False to unmark.

        Returns:
            Any: The result of the bulk write operation.
        """
        if not var_ids:
            return OperationResult.empty()

        object_ids: list[ObjectId] = []
        for vid in var_ids:
            try:
                object_ids.append(ObjectId(vid))
            except Exception:
                continue

        if not object_ids:
            return OperationResult.empty(requested_count=len(var_ids))

        try:
            return OperationResult.from_update(
                self.get_collection().update_many(
                    {"_id": {"$in": object_ids}},
                    {"$set": {"irrelevant": irrelevant}},
                ),
                requested_count=len(object_ids),
            )
        except Exception as exc:
            return OperationResult.failed(str(exc), requested_count=len(object_ids))

    def mark_blacklisted(self, var_id: str, blacklisted: bool) -> OperationResult:
        """Set the sample-specific blacklist state for a structural finding."""
        return OperationResult.from_update(
            self.get_collection().update_one(
                {"_id": ObjectId(var_id)},
                {"$set": {"blacklisted": blacklisted}},
            )
        )

    def mark_blacklisted_bulk(self, var_ids: list[str], blacklisted: bool) -> OperationResult:
        """Set sample-specific blacklist state for multiple structural findings."""
        if not var_ids:
            return OperationResult.empty()

        object_ids: list[ObjectId] = []
        for var_id in var_ids:
            try:
                object_ids.append(ObjectId(var_id))
            except Exception:
                continue
        if not object_ids:
            return OperationResult.empty(requested_count=len(var_ids))

        try:
            return OperationResult.from_update(
                self.get_collection().update_many(
                    {"_id": {"$in": object_ids}},
                    {"$set": {"blacklisted": blacklisted}},
                ),
                requested_count=len(object_ids),
            )
        except Exception as exc:
            return OperationResult.failed(str(exc), requested_count=len(object_ids))

    def mark_noteworthy(self, var_id: str, noteworthy: bool) -> Any:
        """
        Mark / Unmark a variant as noteworthy.

        This method updates the `noteworthy` field of a document in the collection
        to indicate whether the variant is considered noteworthy. A noteworthy variant
        is interesting but may not be used for reporting; it can be referenced for
        future purposes.

        Args:
            var_id (str): The unique identifier of the variant or document.
            noteworthy (bool): A boolean value indicating whether to mark the variant as noteworthy.

        Returns:
            Any: The result of the update operation.
        """
        return OperationResult.from_update(
            self.get_collection().update_one(
                {"_id": ObjectId(var_id)},
                {"$set": {"noteworthy": noteworthy}},
            )
        )

    def add_comment(self, comment_doc: dict) -> Any:
        """
        Add a comment to a variant.

        This method inserts a comment document into the collection associated
        with the handler. The comment document should include all necessary
        fields such as the comment text, author, and timestamp.

        Args:
            comment_doc (dict): A dictionary containing the comment details to
                                be added to the collection.

        Returns:
            Any: The result of the insert operation.
        """
        return OperationResult.from_insert_one(self.get_collection().insert_one(comment_doc))

    def toggle_active(self, doc_id: str, active: bool) -> Any:
        """
        Toggle the active status of a document.

        This method updates the `active` field of a document in the collection
        to indicate whether it is currently active or not.

        Args:
            doc_id (str): The unique identifier of the document to update.
            active (bool): A boolean value indicating whether to set the document as active.

        Returns:
            Any: The result of the update operation.
        """
        return OperationResult.from_update(
            self.get_collection().update_one({"_id": doc_id}, {"$set": {"active": active}})
        )
