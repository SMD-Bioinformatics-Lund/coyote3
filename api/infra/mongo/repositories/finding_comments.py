"""Repository for comments attached to clinical findings."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from bson.objectid import ObjectId

from api.contracts.operations import OperationResult
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.core.annotation_identity import finding_comment_identity
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now
from api.infra.request_context import current_username

FindingType = Literal["small_variant", "cnv", "fusion", "translocation"]


class FindingCommentsRepository(BaseRepository):
    """Persist finding comments independently from the finding documents."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.finding_comments_collection)

    def ensure_indexes(self) -> None:
        collection = self.get_collection()
        collection.create_index(
            [("finding_type", 1), ("finding_oid", 1), ("time_created", 1)],
            name="finding_type_oid_time",
        )
        collection.create_index(
            [("sample_oid", 1), ("finding_type", 1), ("time_created", 1)],
            name="sample_oid_type_time",
        )
        collection.create_index(
            [("sample_name", 1), ("finding_type", 1), ("time_created", 1)],
            name="sample_name_type_time",
        )
        collection.create_index([("hidden", 1)], name="hidden_1")

    @staticmethod
    def _object_id(value: Any) -> ObjectId:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def _sample_name(self, finding: dict[str, Any]) -> str | None:
        name = finding.get("sample_name") or finding.get("SAMPLE_NAME")
        if name:
            return str(name)
        sample_oid = finding.get("SAMPLE_ID")
        if not sample_oid:
            return None
        return self.adapter.sample_repository.get_sample_name(str(sample_oid))

    def add_finding_comment(
        self,
        *,
        finding: dict[str, Any],
        finding_type: FindingType,
        comment_doc: dict[str, Any],
    ) -> ObjectId:
        comment = dict(comment_doc or {})
        comment["_id"] = self._object_id(comment.get("_id") or ObjectId())
        comment["finding_oid"] = self._object_id(finding["_id"])
        comment["finding_type"] = finding_type
        comment["sample_oid"] = self._object_id(finding["SAMPLE_ID"])
        comment["sample_name"] = self._sample_name(finding)
        for key, value in finding_comment_identity(finding, finding_type).items():
            if comment.get(key) in (None, ""):
                comment[key] = value
        comment.setdefault("author", current_username())
        comment.setdefault("hidden", 0)
        comment.setdefault("time_created", utc_now())
        normalized = normalize_collection_document("finding_comments", comment)
        self.get_collection().insert_one(normalized)
        return comment["_id"]

    def set_hidden(
        self,
        *,
        finding_oid: str,
        finding_type: FindingType,
        comment_id: str,
        hidden: bool,
    ) -> None:
        query = {
            "_id": self._object_id(comment_id),
            "finding_oid": self._object_id(finding_oid),
            "finding_type": finding_type,
        }
        if hidden:
            update = {
                "$set": {
                    "hidden": 1,
                    "hidden_by": current_username(),
                    "time_hidden": utc_now(),
                }
            }
        else:
            update = {
                "$set": {"hidden": 0},
                "$unset": {"hidden_by": "", "time_hidden": ""},
            }
        self.get_collection().update_one(query, update)

    def has_hidden_comments(self, *, finding_oid: str, finding_type: FindingType) -> bool:
        return (
            self.get_collection().count_documents(
                {
                    "finding_oid": self._object_id(finding_oid),
                    "finding_type": finding_type,
                    "hidden": {"$in": [1, True]},
                },
                limit=1,
            )
            > 0
        )

    def list_comments(
        self,
        *,
        finding_oid: Any,
        finding_type: FindingType,
        include_hidden: bool = True,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "finding_oid": self._object_id(finding_oid),
            "finding_type": finding_type,
        }
        if not include_hidden:
            query["hidden"] = {"$in": [0, False, None]}
        return list(self.get_collection().find(query).sort([("time_created", 1), ("_id", 1)]))

    def attach_comments(
        self, finding: dict[str, Any] | None, finding_type: FindingType
    ) -> dict[str, Any] | None:
        if not finding:
            return finding
        hydrated = dict(finding)
        hydrated["comments"] = self.list_comments(
            finding_oid=finding["_id"], finding_type=finding_type
        )
        return hydrated

    def attach_comments_many(
        self, findings: list[dict[str, Any]], finding_type: FindingType
    ) -> list[dict[str, Any]]:
        finding_oids = [self._object_id(row["_id"]) for row in findings if row.get("_id")]
        grouped: dict[ObjectId, list[dict[str, Any]]] = defaultdict(list)
        if finding_oids:
            cursor = (
                self.get_collection()
                .find({"finding_type": finding_type, "finding_oid": {"$in": finding_oids}})
                .sort([("time_created", 1), ("_id", 1)])
            )
            for comment in cursor:
                grouped[self._object_id(comment["finding_oid"])].append(comment)
        hydrated = []
        for row in findings:
            finding_oid = row.get("_id")
            comments = grouped.get(self._object_id(finding_oid), []) if finding_oid else []
            hydrated.append({**row, "comments": comments})
        return hydrated

    def delete_sample_finding_comments(self, sample_oid: str) -> OperationResult:
        return OperationResult.from_delete(
            self.get_collection().delete_many({"sample_oid": self._object_id(sample_oid)})
        )
