"""Publish committed configuration, assigned-review and assay-group report notifications."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from coyote3.application.notifications.access import SampleNotificationAccess
from coyote3.application.notifications.service import NotificationService
from coyote3.config.policy import get_runtime_environment


class ActivityNotificationService:
    """Deliver committed events once; retries preserve recipients' existing read state."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        config: dict[str, Any],
        activity_repository: Any,
        sample_access: SampleNotificationAccess,
    ) -> "ActivityNotificationService":
        """Bind activity sources to their configured database endpoints.

        Args:
            store: Initialized application, identity and knowledgebase repositories.
            config: Runtime deployment settings, including retention and environment.
            activity_repository: Entry-point supplied reader for committed activity.
            sample_access: Current clinical authorization resolver.

        Returns:
            A delivery service without SMTP side effects.
        """
        return cls(
            activity_repository=activity_repository,
            notifications=NotificationService.from_store(
                store,
                retention_days=int(config.get("NOTIFICATION_RETENTION_DAYS", 180)),
                sample_access=sample_access,
            ),
            users=store.user_repository,
            samples=store.sample_repository,
            environment=get_runtime_environment(config),
            sample_access=sample_access,
            app_prefix=str(config.get("SCRIPT_NAME") or ""),
        )

    def __init__(
        self,
        *,
        activity_repository: Any,
        notifications: NotificationService,
        users: Any,
        samples: Any,
        environment: str,
        sample_access: SampleNotificationAccess,
        app_prefix: str = "",
    ):
        """Configure source readers, recipient resolution and notification persistence.

        Args:
            activity_repository: Reads committed events awaiting a notification.
            notifications: Recipient-scoped notification writer.
            users: Active account repository, including assigned scope attributes.
            samples: Sample repository for resolving report ownership.
            environment: Deployment environment used to select source events.
            sample_access: Current clinical read policy used before addressing a report notice.
            app_prefix: Deployment URL prefix for linked review requests; empty means root.
        """
        self.activity = activity_repository
        self.notifications = notifications
        self.users = users
        self.samples = samples
        self.environment = environment
        self.sample_access = sample_access
        self.app_prefix = f"/{app_prefix.strip('/')}" if app_prefix.strip("/") else ""

    def deliver(self) -> int:
        """Publish a bounded batch after business commits and audit-outbox delivery.

        Returns:
            Number of processed events, including reports with no eligible recipients.

        Notes:
            Failures propagate to the worker. The next delivery retries the same event
            identity without duplicating notices or resetting read/dismissed state.
            Missing samples produce an empty audience; their identity is not broadcast.
        """
        now = datetime.now(timezone.utc)
        events = self.activity.pending(
            since=now - timedelta(days=self.notifications.retention_days),
            environment=self.environment,
        )
        for event in events:
            resource = event.get("resource") or {}
            metadata = event.get("metadata") or {}
            audience, recipients = "all", []
            title = "Shared configuration updated"
            message = f"{resource.get('type', 'Configuration')}: {resource.get('name') or resource.get('id') or ''}"
            if event["event_type"] == "report.saved":
                sample = self.samples.get_notification_sample(str(metadata.get("sample_oid") or ""))
                recipients = self._report_recipients(sample) if sample else []
                audience = "selected"
                title = "Sample reported"
                message = f"Report {metadata.get('report_num', '')} saved for {(sample or {}).get('name', 'sample')}."
                resource = {"type": "sample", "id": str(metadata.get("sample_oid") or "")}
            elif event["event_type"] == "assay_setup.submit":
                reviewer = str(metadata.get("reviewer") or "").strip().lower()
                audience, recipients = "selected", [reviewer] if reviewer else []
                title = "Assay setup review requested"
                message = (
                    f"Review assay setup {metadata.get('asp_id') or resource.get('id') or ''}."
                )
            elif resource.get("type") == "knowledgebase":
                title = "Knowledgebase updated"
                message += f" {metadata.get('release') or ''}"
            else:
                action = metadata.get("action") or "updated"
                label = {
                    "asp": "Assay",
                    "aspc": "Assay configuration",
                    "genelist": "Gene list (ISGL)",
                    "assay_group": "Assay group",
                    "diagnosis": "Diagnosis",
                    "assay_diagnosis": "Assay diagnosis",
                    "assay_setup": "Assay setup",
                }.get(str(resource.get("type") or ""), "Shared configuration")
                title = f"{label} {action}"
                message = (
                    f"{label} {resource.get('name') or resource.get('id') or ''} was {action}."
                )
            notification_resource = {
                key: value for key, value in resource.items() if key in {"type", "id", "name"}
            }
            if event["event_type"] == "assay_setup.submit":
                notification_resource["uri"] = (
                    f"{self.app_prefix}/admin/assay-setups?setup={resource['id']}"
                )
            self.notifications.create_notification(
                audience=audience,
                recipients=recipients,
                tone="info",
                category="application",
                title=title,
                message=message,
                source="Application activity",
                created_by=(event.get("actor") or {}).get("username") or "system",
                resource=notification_resource,
                event_id=event["_id"],
                created_at=event.get("occurred_at"),
            )
        self.activity.acknowledge()
        return len(events)

    def _report_recipients(self, sample: dict[str, Any]) -> list[str]:
        """Select active assay-group members whose sample scope permits access.

        Args:
            sample: Saved report's sample with assay, group and environment identifiers.

        Returns:
            Canonical usernames; an absent group never expands to all users.
        """
        group = str(sample.get("asp_group") or "").strip().lower()
        if not group:
            return []
        recipients = set()
        for document in self.users.list_active_users_for_notifications():
            groups = {str(value).lower() for value in document.get("asp_groups") or []}
            if group not in groups and "*" not in groups:
                continue
            user = SimpleNamespace(**document)
            if self.sample_access.sample_predicate(user)(sample):
                recipients.add(str(document["username"]).strip().lower())
        return sorted(recipients)
