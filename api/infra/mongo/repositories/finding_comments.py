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
        """Bind the independent finding-comment collection.

        Args:
            adapter: Mongo adapter exposing ``finding_comments_collection`` and
                the sample repository used to resolve missing sample names.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.finding_comments_collection)

    def ensure_indexes(self) -> None:
        """Create finding, sample, chronological, and hidden-comment lookup indexes."""
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
        """Convert a comment or owner identifier to MongoDB's ObjectId.

        Args:
            value: ObjectId or value whose string form is a valid ObjectId.

        Returns:
            Existing or parsed ObjectId.

        Raises:
            InvalidId: If the string representation is not a valid ObjectId.
        """
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def _sample_name(self, finding: dict[str, Any]) -> str | None:
        """Resolve a sample name from the finding or its sample repository entry.

        Args:
            finding: Finding with optional sample_name, SAMPLE_NAME, and SAMPLE_ID fields.

        Returns:
            Explicit name, otherwise the sample repository lookup result; ``None``
            when neither a name nor a sample ID is present.
        """
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
        """Normalize and insert a comment with finding and sample ownership.

        Args:
            finding: Owner document with ``_id`` and ``SAMPLE_ID`` plus identity fields.
            finding_type: Small-variant, CNV, fusion, or translocation discriminator.
            comment_doc: Comment fields copied before ownership and missing defaults
                are applied; an absent or falsey comment ID is generated.

        Returns:
            ObjectId of the inserted comment.

        Raises:
            KeyError: If the finding lacks required owner identifiers.
            InvalidId: If a comment or owner identifier cannot be parsed.
            ValidationError: If the normalized comment violates its collection contract.

        Notes:
            Missing author, hidden state, and creation time default to the current
            username, zero, and current UTC time. For each identity field supplied by
            finding enrichment, missing values, ``None``, and empty strings are replaced
            with the derived value; other existing values are retained.
        """
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
        """Hide or restore a comment only when its finding ownership matches.

        Args:
            finding_oid: Serialized owner ObjectId.
            finding_type: Owner finding discriminator.
            comment_id: Serialized comment ObjectId.
            hidden: Whether to hide the comment; restoring removes hide metadata.

        Raises:
            InvalidId: If either identifier cannot be parsed.

        Notes:
            Hiding records the current username and UTC time. No match is a no-op.
        """
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
        """Check for at least one hidden comment on a finding.

        Args:
            finding_oid: Serialized owner ObjectId.
            finding_type: Owner finding discriminator.

        Returns:
            Whether a matching comment has hidden state one or true.

        Raises:
            InvalidId: If the owner identifier cannot be parsed.
        """
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
        """List a finding's comments in ascending creation-time and ID order.

        Args:
            finding_oid: Owner ObjectId or its serialized form.
            finding_type: Owner finding discriminator.
            include_hidden: Include all visibility states by default; false selects
                zero, false, null, or missing hidden values.

        Returns:
            Matching comment documents, including an empty list when none exist.

        Raises:
            InvalidId: If the owner identifier cannot be parsed.
        """
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
        """Copy a finding and attach all its comments, including hidden ones.

        Args:
            finding: Owner document with ``_id``; ``None`` or an empty dict is returned unchanged.
            finding_type: Owner finding discriminator.

        Returns:
            Finding copy with chronologically ordered comments, or the falsey input.

        Raises:
            InvalidId: If the finding identifier cannot be parsed.
        """
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
        """Attach comments to finding copies using one query for all owner IDs.

        Args:
            findings: Owner documents; rows without a truthy ID receive an empty list.
            finding_type: Shared owner finding discriminator.

        Returns:
            Copies in input order, with all comments ordered by creation time and ID,
            including hidden comments.

        Raises:
            InvalidId: If a supplied truthy finding ID cannot be parsed.
        """
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
        """Delete every finding comment owned by a sample in one transaction.

        Args:
            sample_oid: Serialized sample ObjectId.

        Returns:
            Deletion counts expressed as an application operation result.

        Raises:
            InvalidId: If the sample identifier cannot be parsed.
        """
        return OperationResult.from_delete(
            self.delete_many_atomic({"sample_oid": self._object_id(sample_oid)})
        )
