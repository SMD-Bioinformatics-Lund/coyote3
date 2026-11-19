# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Shared collection operations, transactions and repository-scoped cache invalidation."""

import logging
from collections.abc import Iterable, Mapping, Sequence
from types import SimpleNamespace
from typing import Any, cast

import pymongo
from bson.objectid import ObjectId
from coyote.application.dashboard.cache import DashboardMetricCache, invalidate_dashboard_metrics
from coyote.contracts.operations import OperationResult
from coyote.domain.selection import Selection
from pymongo.client_session import ClientSession
from pymongo.collection import Collection
from pymongo.results import BulkWriteResult, DeleteResult, InsertManyResult, UpdateResult

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.records import application_record
from coyote_mongo.repositories.mutations import WriteOperation, write_with_audit
from coyote_mongo.results import operation_from_insert_one, operation_from_update
from coyote_mongo.selection import compile_selection


class BaseRepository:
    """Base repository for collection-scoped MongoDB operations."""

    def __init__(self, adapter: object) -> None:
        """Retain the adapter and its optional runtime context before binding a collection.

        Args:
            adapter: Persistence host supplying the collection and, for audited or cached
                operations, an app context with audit identity and cache configuration.
        """
        self.adapter = adapter
        self.app = getattr(
            adapter,
            "app",
            SimpleNamespace(logger=logging.getLogger("coyote_mongo.repositories")),
        )

        self.repository_collection: Collection[dict[str, Any]] | None = None

    @property
    def audit_context(self) -> AuditContext:
        """Return the deployment identity explicitly supplied by this repository's host."""
        return self.app.audit

    def set_collection(self, collection: Collection[dict[str, Any]]) -> None:
        """Bind the repository to a MongoDB collection.

        Args:
            collection: Driver collection whose documents this repository owns.
        """
        self.repository_collection = collection

    def write(self, collection: Any, operation: WriteOperation, *args: Any, **options: Any) -> Any:
        """Persist data and its audit receipt using this repository's deployment identity."""
        return write_with_audit(collection, operation, *args, context=self.audit_context, **options)

    def preview_sample_findings(
        self, sample_id: str, query: Selection, limit: int = 10001
    ) -> list[dict[str, Any]]:
        """Read bounded finding candidates for a non-persisting rule comparison.

        Args:
            sample_id: Authorized sample identity, independently enforced on the query.
            query: Database-independent clinical selection; never raw storage syntax.
            limit: Maximum candidates including the overflow sentinel; defaults to 10001.

        Returns:
            Application records with string identities, without comment hydration.
            No stored records are changed.

        Raises:
            PyMongoError: MongoDB fails or exceeds the five-second query limit.
        """
        return [
            application_record(record)
            for record in (
                self.get_collection()
                .find(
                    {"$and": [{"SAMPLE_ID": str(sample_id)}, compile_selection(query)]},
                    {"comments": 0},
                )
                .sort("_id", 1)
                .limit(limit)
                .max_time_ms(5000)
            )
        ]

    def get_collection(self) -> Collection[dict[str, Any]]:
        """Return the MongoDB collection bound to this repository.

        Returns:
            The collection previously supplied to set_collection.

        Raises:
            NotImplementedError: No collection has been bound by the concrete repository.
        """
        if self.repository_collection is not None:
            return self.repository_collection
        raise NotImplementedError("get_collection or set_collection must be implemented")

    def _ensure_sample_finding_indexes(self) -> None:
        """Ensure the shared sample lookup and review-flag indexes on this collection.

        Notes:
            Index names and key order are stable storage contracts. Concrete finding
            repositories explicitly opt in and retain their additional indexes.
        """
        collection = self.get_collection()
        collection.create_index([("SAMPLE_ID", 1)], name="sample_id_1", background=True)
        for flag in ("interesting", "fp", "irrelevant"):
            collection.create_index(
                [("SAMPLE_ID", 1), (flag, 1)],
                name=f"sample_id_1_{flag}_1",
                background=True,
            )

    def update_many_atomic(
        self, selector: Mapping[str, Any], update: Mapping[str, Any] | Sequence[Mapping[str, Any]]
    ) -> UpdateResult:
        """Apply all matching updates in one required transaction.

        Args:
            selector: MongoDB predicate selecting the documents.
            update: MongoDB update operators or an aggregation update pipeline.

        Returns:
            The driver's acknowledged result after the transaction commits.
        """
        return cast(
            UpdateResult, self.write(self.get_collection(), "update_many", selector, update)
        )

    def delete_many_atomic(self, selector: Mapping[str, Any]) -> DeleteResult:
        """Delete matching documents as one commit.

        Args:
            selector: MongoDB predicate selecting the documents.

        Returns:
            The driver's deletion result after the transaction commits.
        """
        return cast(DeleteResult, self.write(self.get_collection(), "delete_many", selector))

    def insert_many_atomic(self, documents: Iterable[Mapping[str, Any]]) -> InsertManyResult:
        """Insert copies of all documents together or abort the entire batch.

        Args:
            documents: Documents to copy and insert within the owning transaction.

        Returns:
            The driver's inserted identities after the transaction commits.
        """
        return cast(
            InsertManyResult,
            self.write(self.get_collection(), "insert_many", [dict(doc) for doc in documents]),
        )

    def bulk_write_atomic(
        self,
        operations: Sequence[
            pymongo.InsertOne[dict[str, Any]]
            | pymongo.ReplaceOne[dict[str, Any]]
            | pymongo.UpdateOne
            | pymongo.UpdateMany
            | pymongo.DeleteOne
            | pymongo.DeleteMany
        ],
        *,
        session: ClientSession | None = None,
    ) -> BulkWriteResult:
        """Join an owning transaction, or start a required transaction for the batch.

        Args:
            operations: Driver operations executed as an unordered bulk write.
            session: Existing owning session; None starts a required transaction.

        Returns:
            The driver's bulk-write result from the supplied or new transaction.
        """

        return cast(
            BulkWriteResult,
            self.write(
                self.get_collection(),
                "bulk_write",
                operations,
                ordered=False,
                session=session,
            ),
        )

    def invalidate_dashboard_metrics(self) -> None:
        """Invalidate dashboard metrics that depend on this collection."""
        adapter = getattr(self, "adapter", None)
        if adapter is not None:
            runtime = getattr(adapter, "app", None)
            cache = getattr(runtime, "cache", None)
            if cache is None:
                return
            config = cast(Mapping[str, Any], getattr(runtime, "config"))
            options = {
                field: int(config[key])
                for field, key in (
                    ("fresh_seconds", "DASHBOARD_METRIC_CACHE_TTL_SECONDS"),
                    ("retention_seconds", "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS"),
                )
                if config.get(key)
            }
            invalidate_dashboard_metrics(
                DashboardMetricCache(cache, **options), collection=self.get_collection().name
            )

    def _invalidate_dashboard_on_change(self, result: OperationResult) -> OperationResult:
        """Invalidate dependent metrics when a write reports changed documents.

        Args:
            result: Write counts to inspect for modifications, deletions, or inserts.

        Returns:
            The same operation result after any required invalidation.
        """
        if result.modified_count or result.deleted_count or result.inserted_count:
            self.invalidate_dashboard_metrics()
        return result

    def set_sample_finding_flag(
        self, *, sample_id: str, resource_ids: list[str], flag: str, value: bool
    ) -> OperationResult:
        """Update an allowed finding flag within one authorized sample.

        Args:
            sample_id: Canonical owning sample identifier, never a display name.
            resource_ids: Finding identifiers whose ownership was checked by the caller.
            flag: Persisted boolean flag field.
            value: Whether the flag is enabled.

        Returns:
            Matched and modified counts for the scoped write.

        Raises:
            ValueError: If the sample or flag is invalid.
            InvalidId: If any finding identifier is malformed; nothing is written.
        """
        if not sample_id or flag not in {
            "fp",
            "interesting",
            "irrelevant",
            "blacklisted",
            "noteworthy",
            "override_blacklist",
        }:
            raise ValueError("A sample and supported finding flag are required")
        object_ids = [ObjectId(identifier) for identifier in resource_ids]
        if not object_ids:
            return OperationResult.empty()
        result = self.update_many_atomic(
            {"_id": {"$in": object_ids}, "SAMPLE_ID": sample_id},
            {"$set": {flag: value}},
        )
        return self._invalidate_dashboard_on_change(
            operation_from_update(result, requested_count=len(object_ids))
        )

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
        return self._invalidate_dashboard_on_change(
            operation_from_update(
                self.write(
                    self.get_collection(),
                    "update_one",
                    {"_id": ObjectId(var_id)},
                    {"$set": {"fp": fp}},
                )
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
            return self._invalidate_dashboard_on_change(
                operation_from_update(
                    self.update_many_atomic(
                        {"_id": {"$in": object_ids}},
                        {"$set": {"fp": fp}},
                    ),
                    requested_count=len(object_ids),
                )
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
        return self._invalidate_dashboard_on_change(
            operation_from_update(
                self.write(
                    self.get_collection(),
                    "update_one",
                    {"_id": ObjectId(var_id)},
                    {"$set": {"interesting": interesting}},
                )
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
        return self._invalidate_dashboard_on_change(
            operation_from_update(
                self.write(
                    self.get_collection(),
                    "update_one",
                    {"_id": ObjectId(var_id)},
                    {"$set": {"irrelevant": irrelevant}},
                )
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
            return self._invalidate_dashboard_on_change(
                operation_from_update(
                    self.update_many_atomic(
                        {"_id": {"$in": object_ids}},
                        {"$set": {"irrelevant": irrelevant}},
                    ),
                    requested_count=len(object_ids),
                )
            )
        except Exception as exc:
            return OperationResult.failed(str(exc), requested_count=len(object_ids))

    def mark_blacklisted(self, var_id: str, blacklisted: bool) -> OperationResult:
        """Set the sample-specific blacklist state for a structural finding."""
        return self._invalidate_dashboard_on_change(
            operation_from_update(
                self.write(
                    self.get_collection(),
                    "update_one",
                    {"_id": ObjectId(var_id)},
                    {"$set": {"blacklisted": blacklisted}},
                )
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
            return self._invalidate_dashboard_on_change(
                operation_from_update(
                    self.update_many_atomic(
                        {"_id": {"$in": object_ids}},
                        {"$set": {"blacklisted": blacklisted}},
                    ),
                    requested_count=len(object_ids),
                )
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
        return self._invalidate_dashboard_on_change(
            operation_from_update(
                self.write(
                    self.get_collection(),
                    "update_one",
                    {"_id": ObjectId(var_id)},
                    {"$set": {"noteworthy": noteworthy}},
                )
            )
        )

    def add_comment(self, comment_doc: dict[str, Any]) -> Any:
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
        return operation_from_insert_one(
            self.write(self.get_collection(), "insert_one", comment_doc)
        )

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
        return operation_from_update(
            self.write(
                self.get_collection(), "update_one", {"_id": doc_id}, {"$set": {"active": active}}
            )
        )
