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
        """Load a comment owner from this finding repository.

        Args:
            finding_id: Serialized finding ObjectId.

        Returns:
            Matching finding document.

        Raises:
            InvalidId: If the identifier is not a valid ObjectId.
            LookupError: If the finding does not exist.
        """
        finding = self.get_collection().find_one({"_id": ObjectId(finding_id)})
        if finding is None:
            raise LookupError(f"{self.finding_type} finding '{finding_id}' does not exist")
        return finding

    def _hydrate_finding_comments(self, finding: dict | None) -> dict | None:
        """Attach comments using this repository's finding type.

        Args:
            finding: Finding document, or ``None`` for an absent lookup result.

        Returns:
            Finding copy with all comments; falsey input is returned unchanged.
        """
        return self.adapter.finding_comment_repository.attach_comments(finding, self.finding_type)

    def hydrate_finding_comments_many(self, findings: list[dict]) -> list[dict]:
        """Attach comments to a batch using this repository's finding type.

        Args:
            findings: Finding documents to hydrate without changing the inputs.

        Returns:
            Copies in input order with comment lists, including hidden comments.
        """
        return self.adapter.finding_comment_repository.attach_comments_many(
            findings, self.finding_type
        )

    def _add_finding_comment(self, finding_id: str, comment: dict) -> None:
        """Resolve the finding and delegate insertion of its comment.

        Args:
            finding_id: Serialized finding ObjectId.
            comment: Comment fields passed to the finding-comment repository.

        Raises:
            InvalidId: If a finding or comment identifier cannot be parsed.
            LookupError: If the finding does not exist.
            ValidationError: If the comment violates its collection contract.
        """
        self.adapter.finding_comment_repository.add_finding_comment(
            finding=self._finding(finding_id),
            finding_type=self.finding_type,
            comment_doc=comment,
        )

    def _set_finding_comment_hidden(self, finding_id: str, comment_id: str, hidden: bool) -> None:
        """Delegate an ownership-scoped change to comment visibility.

        Args:
            finding_id: Serialized owner ObjectId.
            comment_id: Serialized comment ObjectId.
            hidden: Whether to hide the comment or restore its visibility.

        Raises:
            InvalidId: If either identifier cannot be parsed.
        """
        self.adapter.finding_comment_repository.set_hidden(
            finding_oid=finding_id,
            finding_type=self.finding_type,
            comment_id=comment_id,
            hidden=hidden,
        )

    def _has_hidden_finding_comments(self, finding_id: str) -> bool:
        """Check hidden comments for this repository's finding type.

        Args:
            finding_id: Serialized owner ObjectId.

        Returns:
            Whether the comment repository finds a hidden comment for this owner.

        Raises:
            InvalidId: If the identifier cannot be parsed.
        """
        return self.adapter.finding_comment_repository.has_hidden_comments(
            finding_oid=finding_id, finding_type=self.finding_type
        )
