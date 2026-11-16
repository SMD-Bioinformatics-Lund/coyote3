# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validated rule reads and conditional lifecycle persistence."""

from __future__ import annotations

from typing import Any

from coyote.application.common.protected_records import reject_system_managed_change
from coyote.contracts.schemas.clinical_rules import (
    ClinicalRuleSetDoc,
    ClinicalRuleStatus,
)
from coyote.domain.common.errors import api_error
from coyote.domain.common.reporting import (
    utc_now,
)


class RuleRecords:
    """Read validated rule records and perform revision-fenced lifecycle changes."""

    def __init__(self, repository: Any) -> None:
        """Bind the rule-version repository without changing transaction ownership."""
        self.repository = repository

    def get(self, document_id: str) -> ClinicalRuleSetDoc:
        """Load and parse a stored rule version.

        Args:
            document_id: Repository identifier of the version.

        Returns:
            Validated canonical rule document.

        Raises:
            AppError: With status 404 when the version is absent.
            ValidationError: Stored data does not satisfy the canonical schema.
        """
        document = self.repository.get(document_id)
        if document is None:
            raise api_error(404, "Clinical rule-set version was not found")
        return ClinicalRuleSetDoc.model_validate(document)

    def transition(
        self,
        document_id: str,
        *,
        expected_revision: int,
        actor: str,
        reason: str,
        from_statuses: set[str],
        status: ClinicalRuleStatus,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Conditionally change lifecycle state, append its event, and audit it.

        Args:
            document_id: Version to transition.
            expected_revision: Revision read during validation and authorization.
            actor: Login recorded on the lifecycle and audit events.
            reason: Event explanation; blank is stored as None.
            from_statuses: Permitted current statuses passed to the repository.
            status: Target lifecycle state.
            extra: Optional additional update fields, including dotted review fields.

        Returns:
            Parsed and serialized updated version.

        Raises:
            AppError: With status 409 when the conditional transition is refused.
        """
        now = utc_now()
        stored = self.repository.get(document_id)
        if stored is None:
            raise api_error(404, "Clinical rule-set version was not found")
        reject_system_managed_change(stored, resource="reporting rule")
        changes = {"status": status.value, "updated_at": now, **(extra or {})}
        event = {
            "action": status.value,
            "actor": actor,
            "occurred_at": now,
            "reason": reason or None,
        }
        updated = self.repository.transition(
            document_id,
            expected_revision=expected_revision,
            from_statuses=from_statuses,
            changes=changes,
            event=event,
        )
        if updated is None:
            raise api_error(409, f"Clinical rule set cannot transition to {status.value}")
        parsed = ClinicalRuleSetDoc.model_validate(updated)
        return parsed.model_dump(mode="python", by_alias=True)
