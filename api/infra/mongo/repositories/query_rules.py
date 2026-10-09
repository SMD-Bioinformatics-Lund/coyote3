"""Transactional storage of governed query-policy release versions."""

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from api.contracts.schemas.query_rules import QueryRuleScope
from api.domain.common.errors import api_error
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repositories.query_rule_revisions import (
    QueryRuleRevisionRepository,
    build_query_revision,
)
from api.infra.mongo.transactions import run_transaction


class QueryRuleRepository(BaseRepository):
    """Retain release history and allow one published version per exact scope."""

    def __init__(self, adapter: Any) -> None:
        """Bind query-rule storage on the application MongoDB endpoint.

        Args:
            adapter: Configured adapter exposing the query-rule collection.
        """
        super().__init__(adapter)
        self.set_collection(adapter.query_rule_sets_collection)
        self.revisions = adapter.query_rule_revisions_collection
        self.history = QueryRuleRevisionRepository(adapter)

    def _snapshot(self, document: dict, action: str, session: Any) -> None:
        """Append a contiguous revision within the owning write transaction.

        Args:
            document: Stored post-operation version.
            action: Lifecycle event being recorded.
            session: Session shared with the rule and audit writes.

        Raises:
            RuntimeError: A baseline is missing or the revision sequence is inconsistent.
        """
        previous = self.revisions.find_one(
            {"rule_oid": str(document["_id"])}, sort=[("revision", -1)], session=session
        )
        if (previous is None and document["revision"] != 1) or (
            previous is not None and previous["revision"] + 1 != document["revision"]
        ):
            raise RuntimeError("Query rule revision baseline missing or sequence inconsistent")
        self.revisions.insert_one(
            build_query_revision(document, action, previous["revision_hash"] if previous else None),
            session=session,
        )

    def ensure_indexes(self) -> None:
        """Enforce scope/version uniqueness and one published version per scope."""
        collection = self.get_collection()
        collection.create_index(
            [("scope_key", 1), ("version", 1)], unique=True, name="query_rule_scope_version"
        )
        collection.create_index(
            [("scope_key", 1)],
            unique=True,
            partialFilterExpression={"status": "published"},
            name="query_rule_published_scope",
        )
        collection.create_index(
            [("status", 1), ("scope.assay_group", 1), ("scope.analysis", 1), ("scope.intent", 1)],
            name="status_1_scope.assay_group_1_scope.analysis_1_scope.intent_1",
        )

    def list(self) -> list[dict]:
        """List retained versions in scope and descending version order.

        Returns:
            Stored documents across all lifecycle states, or an empty list.
        """
        return list(self.get_collection().find().sort([("scope_key", 1), ("version", -1)]))

    def get(self, identifier: str) -> dict | None:
        """Read a saved policy version.

        Args:
            identifier: Serialized MongoDB ObjectId of the version.

        Returns:
            Stored document, or None for an unknown or malformed identifier.
        """
        try:
            oid = ObjectId(identifier)
        except (InvalidId, TypeError):
            return None
        return self.get_collection().find_one({"_id": oid})

    def next_version(self, scope_key: str) -> int:
        """Propose the next version; the unique index detects competing creation.

        Args:
            scope_key: Canonical group/assay/subpanel/analysis/intent identity.

        Returns:
            One greater than the greatest retained version, or 1 for a new scope.
        """
        row = self.get_collection().find_one({"scope_key": scope_key}, sort=[("version", -1)])
        return int(row["version"]) + 1 if row else 1

    def published_for(self, scope: dict) -> list[dict]:
        """Read published ancestors without matching another assay or subpanel.

        Args:
            scope: Validated scope mapping; absent/null assay and subpanel mean
                the corresponding level was not selected.

        Returns:
            Unordered published versions at the requested scope and its ancestors.
        """
        selected = QueryRuleScope.model_validate(scope)
        ancestors = [QueryRuleScope(analysis=selected.analysis, intent=selected.intent)]
        if selected.assay_group:
            ancestors.append(
                QueryRuleScope(
                    assay_group=selected.assay_group,
                    analysis=selected.analysis,
                    intent=selected.intent,
                )
            )
        if selected.asp_id:
            ancestors.append(
                QueryRuleScope(
                    assay_group=selected.assay_group,
                    asp_id=selected.asp_id,
                    analysis=selected.analysis,
                    intent=selected.intent,
                )
            )
        if selected.subpanel_id:
            ancestors.append(selected)
        return list(
            self.get_collection().find(
                {
                    "status": "published",
                    "scope.analysis": scope["analysis"],
                    "scope.intent": scope["intent"],
                    "query_id": {"$in": [ancestor.key() for ancestor in ancestors]},
                }
            )
        )

    def create(self, document: dict) -> dict:
        """Insert a draft and its audit receipt atomically; reject version races.

        Args:
            document: Validated draft including its scope, proposed version and author.

        Returns:
            Persisted draft with its MongoDB identity.

        Raises:
            AppError: A competing creation already claimed the scope/version pair.
            PyMongoError: The transaction or its audit receipt cannot be committed.
        """
        collection = self.get_collection()
        document = dict(document)
        document.setdefault("_id", ObjectId())

        def write(session):
            """Persist draft creation and traceability in the same transaction."""
            collection.insert_one(document, session=session)
            self._snapshot(document, "created", session)
            enqueue_audit(
                collection.database,
                session,
                event_type="query_rule.created",
                resource_type="query_rule",
                resource_id=document["_id"],
                actor=document["created_by"],
            )
            return document

        try:
            return run_transaction(collection.database.client, write)
        except DuplicateKeyError as error:
            raise api_error(
                409, "A concurrent rule version was created; refresh and retry"
            ) from error

    def change(self, identifier: str, revision: int, status: str, values: dict, actor: str) -> dict:
        """Apply a conditional edit or transition with transactional publication and audit.

        Args:
            identifier: Serialized identity of the version inspected by the operator.
            revision: Expected current revision, incremented on a successful write.
            status: Required source lifecycle state.
            values: Service-validated fields to set; never a raw HTTP update document.
            actor: Authenticated account performing the change.

        Returns:
            Updated document from the committed transaction attempt.

        Raises:
            AppError: Identity is malformed, revision/state changed, or publication
                conflicts with another writer.
            PyMongoError: A persistence or audit failure aborts the transaction.

        Notes:
            Publication retires the prior release at this exact scope in the same
            transaction. Retry callbacks perform database operations only.
        """
        collection = self.get_collection()
        try:
            oid = ObjectId(identifier)
        except (InvalidId, TypeError) as error:
            raise api_error(404, "Query rule version not found") from error

        def write(session):
            """Retire a superseded publication and update only the inspected revision."""
            previous = collection.find_one(
                {"_id": oid, "revision": revision, "status": status}, session=session
            )
            if previous is None:
                raise api_error(409, "Query rule changed or is not in the required state; refresh")
            if values.get("status") == "published":
                retiring = list(
                    collection.find(
                        {"scope_key": previous["scope_key"], "status": "published"}, session=session
                    )
                )
                collection.update_many(
                    {"scope_key": previous["scope_key"], "status": "published"},
                    {
                        "$set": {
                            "status": "retired",
                            "updated_by": actor,
                            "updated_on": values["updated_on"],
                            "reason": "Superseded by published version " + str(previous["version"]),
                        },
                        "$inc": {"revision": 1},
                    },
                    session=session,
                )
                for old in retiring:
                    retired = collection.find_one({"_id": old["_id"]}, session=session)
                    self._snapshot(retired, "superseded", session)
            result = collection.find_one_and_update(
                {"_id": oid, "revision": revision, "status": status},
                {"$set": values, "$inc": {"revision": 1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if result is None:
                raise api_error(409, "Query rule changed; refresh")
            self._snapshot(result, values.get("status", "updated"), session)
            enqueue_audit(
                collection.database,
                session,
                event_type="query_rule." + values.get("status", "updated"),
                resource_type="query_rule",
                resource_id=oid,
                actor=actor,
                metadata={
                    "scope_key": previous["scope_key"],
                    "version": previous["version"],
                    "revision": result["revision"],
                    "reason": values.get("reason", ""),
                },
            )
            return result

        try:
            return run_transaction(collection.database.client, write)
        except DuplicateKeyError as error:
            raise api_error(
                409, "A competing publication changed this scope; refresh and retry"
            ) from error

    def delete_draft(self, identifier: str, revision: int, actor: str, reason: str) -> dict:
        """Delete only the inspected draft, preserving published and approved versions.

        Args:
            identifier: Version ObjectId selected by the operator.
            revision: Optimistic concurrency revision.
            actor: Authenticated editor.
            reason: Required explanation retained in the audit receipt.

        Returns:
            Deleted draft for the service response.

        Raises:
            AppError: Version identity, state or revision does not permit deletion.
        """
        try:
            oid = ObjectId(identifier)
        except (InvalidId, TypeError) as error:
            raise api_error(404, "Query rule version not found") from error
        collection = self.get_collection()

        def write(session):
            """Remove the draft and private snapshots with an atomic audit receipt."""
            deleted = collection.find_one_and_delete(
                {"_id": oid, "revision": revision, "status": "draft"}, session=session
            )
            if deleted is None:
                raise api_error(409, "Only an unchanged draft can be deleted")
            self.revisions.delete_many({"rule_oid": str(oid)}, session=session)
            enqueue_audit(
                collection.database,
                session,
                event_type="query_rule.draft_deleted",
                resource_type="query_rule",
                resource_id=oid,
                actor=actor,
                metadata={"scope_key": deleted["scope_key"], "reason": reason},
            )
            return deleted

        return run_transaction(collection.database.client, write)
