# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Clinical review eligibility, independent assignments and notifications."""

from __future__ import annotations

from typing import Any

from coyote.contracts.schemas.clinical_rules import (
    ClinicalRuleSetDoc,
)
from coyote.domain.common.errors import api_error


class ReviewAssignments:
    """Resolve independent review assignments and their workflow notifications."""

    def __init__(
        self,
        *,
        user_repository: Any = None,
        role_repository: Any = None,
        notification_service: Any = None,
    ) -> None:
        """Bind identity lookups and optional durable notifications."""
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.notification_service = notification_service

    def eligible_users(self, permission: str) -> list[dict[str, str]]:
        """Return active accounts assigned a role with the requested capability."""
        if self.user_repository is None or self.role_repository is None:
            return []
        role_ids = [
            str(role.get("role_id") or "").strip()
            for role in self.role_repository.get_all_roles_plus_permissions()
            if permission in set(role.get("permissions") or [])
        ]
        if not role_ids:
            return []
        users = self.user_repository.list_active_users_for_notifications(role_ids=role_ids)
        return [
            {
                "username": str(user.get("username") or "").strip().lower(),
                "name": str(user.get("fullname") or user.get("username") or "").strip(),
            }
            for user in users
            if str(user.get("username") or "").strip()
        ]

    def options(self) -> dict[str, list[dict[str, str]]]:
        """List active users eligible for clinical review and publication.

        Returns:
            Clinical reviewer and publisher choices; empty without identity repositories.
        """
        return {
            "clinical_reviewers": self.eligible_users("clinical_rules:clinical_review"),
            "publishers": self.eligible_users("clinical_rules:publish"),
        }

    def validate(
        self, username: str | None, permission: str, *, label: str, exclude: str | None = None
    ) -> str:
        """Require an active assignee with the requested role capability.

        Args:
            username: Proposed login; None or blank is rejected.
            permission: Capability required through role membership.
            label: Assignee role label used in error messages.
            exclude: Optional login barred from assignment after normalization.

        Returns:
            Stripped, lowercase eligible login.

        Raises:
            AppError: With status 400 for no assignee or 409 for ineligibility/exclusion.
        """
        normalized = str(username or "").strip().lower()
        if not normalized:
            raise api_error(400, f"Assign an eligible {label} before continuing")
        eligible = {item["username"] for item in self.eligible_users(permission)}
        if normalized not in eligible:
            raise api_error(409, f"Assigned {label} is not an active eligible user")
        if normalized == str(exclude or "").strip().lower():
            raise api_error(409, f"The latest content editor cannot be the assigned {label}")
        return normalized

    def notify(
        self, *, recipient: str, title: str, message: str, document: ClinicalRuleSetDoc, actor: str
    ) -> None:
        """Persist a linked workflow notification and queue email when configured.

        Args:
            recipient: Login receiving the notification.
            title: Notification heading.
            message: Workflow request or outcome text.
            document: Version linked from the notification.
            actor: Login recorded as notification creator.
        """
        if self.notification_service is None:
            return
        self.notification_service.create_notification(
            audience="users",
            recipients=[recipient],
            email_recipients=[recipient]
            if getattr(self.notification_service, "email_sender", None)
            else [],
            tone="info",
            category="application",
            title=title,
            message=message,
            source="Clinical reporting rules",
            created_by=actor,
            resource={
                "type": "clinical_rule_set",
                "id": str(document.id_),
                "name": document.name,
                "uri": f"/admin/clinical-rules?rule_set={document.id_}",
            },
        )
