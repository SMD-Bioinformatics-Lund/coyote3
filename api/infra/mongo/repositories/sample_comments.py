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
        super().__init__(adapter)
        self.set_collection(self.adapter.sample_comments_collection)

    def ensure_indexes(self) -> None:
        col = self.get_collection()
        col.create_index([("sample_oid", 1), ("time_created", -1)], name="sample_oid_time")
        col.create_index([("sample_name", 1), ("time_created", -1)], name="sample_name_time")
        col.create_index([("hidden", 1)], name="hidden_1")

    @staticmethod
    def _object_id(value: Any) -> ObjectId:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def add_sample_comment(self, *, sample: dict, comment_doc: dict) -> ObjectId:
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
        return (
            self.get_collection().count_documents(
                {"sample_oid": self._object_id(sample_oid), "hidden": {"$in": [1, True]}},
                limit=1,
            )
            > 0
        )

    def get_latest_sample_comment(self, sample_oid: str) -> dict | None:
        return self.get_collection().find_one(
            {"sample_oid": self._object_id(sample_oid)},
            sort=[("time_created", -1), ("_id", -1)],
        )

    def list_sample_comments(self, sample_oid: str, *, include_hidden: bool = True) -> list[dict]:
        query: dict[str, Any] = {"sample_oid": self._object_id(sample_oid)}
        if not include_hidden:
            query["hidden"] = {"$in": [0, False, None]}
        return list(self.get_collection().find(query).sort("time_created", -1))

    def delete_sample_comments(self, sample_oid: str) -> OperationResult:
        """Delete comments owned by a sample."""
        return OperationResult.from_delete(
            self.get_collection().delete_many({"sample_oid": self._object_id(sample_oid)})
        )
