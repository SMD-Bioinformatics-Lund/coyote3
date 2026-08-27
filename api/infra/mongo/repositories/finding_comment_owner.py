"""Shared finding-comment behavior for clinical finding repositories."""

from __future__ import annotations

from typing import Any

from bson.objectid import ObjectId

from api.infra.mongo.repositories.finding_comments import FindingType


class FindingCommentOwnerMixin:
    """Delegate comment persistence to the first-class comment repository."""

    finding_type: FindingType
    adapter: Any

    def _finding(self, finding_id: str) -> dict[str, Any]:
        finding = self.get_collection().find_one({"_id": ObjectId(finding_id)})
        if finding is None:
            raise LookupError(f"{self.finding_type} finding '{finding_id}' does not exist")
        return finding

    def _hydrate_finding_comments(self, finding: dict | None) -> dict | None:
        return self.adapter.finding_comment_repository.attach_comments(finding, self.finding_type)

    def hydrate_finding_comments_many(self, findings: list[dict]) -> list[dict]:
        return self.adapter.finding_comment_repository.attach_comments_many(
            findings, self.finding_type
        )

    def _add_finding_comment(self, finding_id: str, comment: dict) -> None:
        self.adapter.finding_comment_repository.add_finding_comment(
            finding=self._finding(finding_id),
            finding_type=self.finding_type,
            comment_doc=comment,
        )

    def _set_finding_comment_hidden(self, finding_id: str, comment_id: str, hidden: bool) -> None:
        self.adapter.finding_comment_repository.set_hidden(
            finding_oid=finding_id,
            finding_type=self.finding_type,
            comment_id=comment_id,
            hidden=hidden,
        )

    def _has_hidden_finding_comments(self, finding_id: str) -> bool:
        return self.adapter.finding_comment_repository.has_hidden_comments(
            finding_oid=finding_id, finding_type=self.finding_type
        )
