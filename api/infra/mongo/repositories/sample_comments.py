"""Repository for sample-level comments."""

from __future__ import annotations

from typing import Any

from bson.objectid import ObjectId

from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now
from api.infra.request_context import current_username


class SampleCommentsRepository(BaseRepository):
    """Persist sample-level comments as first-class documents."""

    def __init__(self, adapter):
        """Bind the sample-level comment collection.

        Args:
            adapter: Mongo adapter exposing ``sample_comments_collection``.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.sample_comments_collection)

    def ensure_indexes(self) -> None:
        """Create sample ID/name chronology and hidden-state lookup indexes."""
        col = self.get_collection()
        col.create_index([("sample_oid", 1), ("time_created", -1)], name="sample_oid_time")
        col.create_index([("sample_name", 1), ("time_created", -1)], name="sample_name_time")
        col.create_index([("hidden", 1)], name="hidden_1")

    @staticmethod
    def _object_id(value: Any) -> ObjectId:
        """Parse a comment or sample identifier as an ObjectId.

        Args:
            value: ObjectId or value whose string form is a valid ObjectId.

        Returns:
            Existing or parsed ObjectId.

        Raises:
            InvalidId: If the string representation is not a valid ObjectId.
        """
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def add_sample_comment(self, *, sample: dict, comment_doc: dict) -> ObjectId:
        """Insert a comment copy with sample ownership and missing defaults filled.

        Args:
            sample: Owner document with ``_id`` and optional name.
            comment_doc: Comment fields; a falsey ID is generated, and absent hidden
                state and creation time default to zero and current UTC time.

        Returns:
            ObjectId of the inserted comment.

        Raises:
            InvalidId: If a comment or sample identifier cannot be parsed.
        """
        comment = dict(comment_doc or {})
        comment_oid = self._object_id(comment.get("_id") or ObjectId())
        comment["_id"] = comment_oid
        comment["sample_oid"] = self._object_id(sample.get("_id"))
        comment["sample_name"] = sample.get("name")
        comment.setdefault("hidden", 0)
        comment.setdefault("time_created", utc_now())
        self.get_collection().insert_one(comment)
        return comment_oid

    def set_hidden(self, *, sample_oid: str, comment_id: str, hidden: bool) -> None:
        """Change visibility only for a comment belonging to the supplied sample.

        Args:
            sample_oid: Serialized sample ObjectId.
            comment_id: Serialized comment ObjectId.
            hidden: Whether to hide; restoring sets hide metadata to ``None``.

        Raises:
            InvalidId: If either identifier cannot be parsed.

        Notes:
            Hiding records the current username and UTC time. No match is a no-op.
        """
        update = {
            "hidden": 1 if hidden else 0,
            "hidden_by": current_username() if hidden else None,
            "time_hidden": utc_now() if hidden else None,
        }
        self.get_collection().update_one(
            {"_id": self._object_id(comment_id), "sample_oid": self._object_id(sample_oid)},
            {"$set": update},
        )

    def hidden_sample_comments(self, sample_oid: str) -> bool:
        """Check whether a sample has any comment marked hidden.

        Args:
            sample_oid: Serialized sample ObjectId.

        Returns:
            Whether a comment has hidden state one or true.

        Raises:
            InvalidId: If the sample identifier cannot be parsed.
        """
        return (
            self.get_collection().count_documents(
                {"sample_oid": self._object_id(sample_oid), "hidden": {"$in": [1, True]}},
                limit=1,
            )
            > 0
        )

    def get_latest_sample_comment(
        self, sample_oid: str, *, include_hidden: bool = False
    ) -> dict | None:
        """Return the newest sample comment eligible for report rendering."""
        query: dict = {"sample_oid": self._object_id(sample_oid)}
        if not include_hidden:
            query["hidden"] = {"$in": [0, False, None]}
        return self.get_collection().find_one(
            query,
            sort=[("time_created", -1), ("_id", -1)],
        )

    def list_sample_comments(self, sample_oid: str, *, include_hidden: bool = True) -> list[dict]:
        """List sample comments with newest creation times first.

        Args:
            sample_oid: Serialized sample ObjectId.
            include_hidden: Include all visibility states by default; false selects
                zero, false, null, or missing hidden values.

        Returns:
            Matching comments, or an empty list when none exist.

        Raises:
            InvalidId: If the sample identifier cannot be parsed.
        """
        query: dict[str, Any] = {"sample_oid": self._object_id(sample_oid)}
        if not include_hidden:
            query["hidden"] = {"$in": [0, False, None]}
        return list(self.get_collection().find(query).sort("time_created", -1))

    def delete_sample_comments(self, sample_oid: str) -> OperationResult:
        """Delete comments owned by a sample."""
        return OperationResult.from_delete(
            self.delete_many_atomic({"sample_oid": self._object_id(sample_oid)})
        )
