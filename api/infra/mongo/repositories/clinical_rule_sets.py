"""Immutable persistence for published clinical reporting rule releases."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from api.contracts.schemas.clinical_rules import ClinicalRuleReleaseDoc, ClinicalRuleSetSource
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now


class ClinicalRuleSetRepository(BaseRepository):
    """Insert and resolve immutable compiled clinical rule releases."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.clinical_rule_sets_collection)

    def ensure_indexes(self) -> None:
        collection = self.get_collection()
        collection.create_index(
            [("rule_set_id", 1), ("version", 1)],
            name="rule_set_version_unique",
            unique=True,
            background=True,
        )
        collection.create_index(
            [("content_hash", 1)],
            name="content_hash_unique",
            unique=True,
            background=True,
        )
        collection.create_index(
            [
                ("source.rule_set.scope.assay_id", 1),
                ("source.rule_set.scope.subpanel_id", 1),
                ("status", 1),
            ],
            name="scope_assay_subpanel_status",
            background=True,
        )

    def publish(
        self,
        *,
        source: ClinicalRuleSetSource,
        content_hash: str,
        source_path: str,
        published_by: str,
    ) -> ClinicalRuleReleaseDoc:
        """Insert one immutable release.

        Re-publishing byte-equivalent canonical content is idempotent. Reusing
        a rule-set/version with different content is rejected.
        """
        existing = self.get_collection().find_one(
            {
                "rule_set_id": source.rule_set.rule_set_id,
                "version": source.rule_set.version,
            }
        )
        if existing:
            if existing.get("content_hash") != content_hash:
                raise ValueError(
                    "The rule-set id/version already exists with different content. "
                    "Increment the authored version before publishing."
                )
            return ClinicalRuleReleaseDoc.model_validate(existing)

        document = {
            "_id": ObjectId(),
            "rule_set_id": source.rule_set.rule_set_id,
            "version": source.rule_set.version,
            "status": "active",
            "schema_version": source.schema_version,
            "content_hash": content_hash,
            "source_path": source_path,
            "source": source.model_dump(mode="python", exclude_none=True),
            "published_by": published_by,
            "published_on": utc_now(),
        }
        try:
            self.get_collection().insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError(
                "A clinical rule release already exists for this version or content hash."
            ) from exc
        return ClinicalRuleReleaseDoc.model_validate(document)

    def get_release(self, release_id: Any) -> ClinicalRuleReleaseDoc | None:
        """Resolve a published release by Mongo object id."""
        try:
            object_id = (
                release_id if isinstance(release_id, ObjectId) else ObjectId(str(release_id))
            )
        except (TypeError, ValueError):
            return None
        document = self.get_collection().find_one({"_id": object_id})
        return ClinicalRuleReleaseDoc.model_validate(document) if document else None

    def get_referenced_release(self, reference: dict[str, Any]) -> ClinicalRuleReleaseDoc | None:
        """Resolve and verify the exact release bound to an ASPC."""
        release = self.get_release(reference.get("release_id"))
        if release is None:
            return None
        expected = (
            reference.get("rule_set_id"),
            reference.get("version"),
            reference.get("content_hash"),
        )
        actual = (release.rule_set_id, release.version, release.content_hash)
        if expected != actual:
            raise ValueError("ASPC clinical rule release reference failed integrity validation")
        return release
