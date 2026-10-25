"""Restricted worker execution of operational application workflows."""

from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from typing import TYPE_CHECKING, Any

from coyote3.application.dashboard.cache import DASHBOARD_METRICS
from coyote3.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote3.application.dashboard.analytics import DashboardService


class MaintenanceServices:
    """Host-owned maintenance integrations; no task runtime or storage driver is required."""

    def __init__(
        self,
        *,
        erase_reports: Callable[[], dict[str, int]],
        finalize_reports: Callable[[], dict[str, int]],
        replay_audit: Callable[[], int],
        deliver_activity: Callable[[], Any],
        deliver_emails: Callable[[], dict[str, Any]],
        retention: Callable[[], dict[str, Any]],
        oncokb: Callable[[], dict[str, Any]],
        dashboard: Callable[[], DashboardService],
        users: Callable[[], list[dict[str, Any]]],
        identity: Callable[[dict[str, Any]], Any],
        logger: Logger,
        checkpoint: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        """Bind fixed maintenance operations and current-user scope projection.

        Args:
            erase_reports: Erases files authorized by committed sample deletion records.
            finalize_reports: Publishes committed, checksum-verified report artifacts.
            replay_audit: Replays pending durable audit delivery; returns the delivered count.
            deliver_activity: Publishes committed activity notifications.
            deliver_emails: Delivers the existing bounded batch of leased emails.
            retention: Runs configured audit and disk-log retention.
            oncokb: Refreshes public reference records from the current HGNC catalog.
            dashboard: Existing metric/cache implementation.
            users: Loads current account records for scope-based metric refresh.
            identity: Projects a stored account into its current verified scope attributes.
            logger: Records per-user/per-metric failures without aborting remaining scopes.
            checkpoint: Optional host archival integration; None disables checkpoint export.
        """
        self.erase_reports, self.finalize_reports = erase_reports, finalize_reports
        self.replay_audit, self.deliver_activity = replay_audit, deliver_activity
        self.deliver_emails, self.retention, self.oncokb = deliver_emails, retention, oncokb
        self.dashboard, self.users, self.identity, self.logger = dashboard, users, identity, logger
        self.checkpoint = checkpoint


class MaintenanceExecution:
    """Execute fixed background operations under a host-owned worker identity."""

    def __init__(self, runtime: ApplicationRuntime, services: MaintenanceServices) -> None:
        """Bind restricted worker authorization and maintenance capabilities."""
        self._runtime, self._services = runtime, services

    def erase_reports(self) -> dict[str, int]:
        """Complete up to 100 report erasures authorized by committed sample deletion."""
        return self._runtime.execute(
            "maintenance.erase_reports",
            ("app.maintenance:run",),
            lambda actor, sample: self._services.erase_reports(),
        )

    def finalize_reports(self) -> dict[str, int]:
        """Resume checksum-verified publication of committed report files."""
        return self._runtime.execute(
            "maintenance.finalize_reports",
            ("app.maintenance:run",),
            lambda actor, sample: self._services.finalize_reports(),
        )

    def replay_audit(self) -> dict[str, Any]:
        """Replay durable audit and activity queues independently of maintenance controls."""
        return self._runtime.execute(
            "maintenance.replay_audit",
            ("app.maintenance:run",),
            lambda actor, sample: {
                "delivered": self._services.replay_audit(),
                "notifications": self._services.deliver_activity(),
            },
        )

    def export_audit_checkpoint(self) -> dict[str, Any]:
        """Verify and archive audit hashes using the host's optional archival destination."""
        return self._runtime.execute(
            "maintenance.export_audit_checkpoint",
            ("app.maintenance:run",),
            lambda actor, sample: (
                self._services.checkpoint()
                if self._services.checkpoint
                else {"status": "not_configured"}
            ),
        )

    def deliver_emails(self) -> dict[str, Any]:
        """Deliver at most ten leased emails without blocking interactive operations."""
        return self._runtime.execute(
            "maintenance.deliver_emails",
            ("app.maintenance:run",),
            lambda actor, sample: self._services.deliver_emails(),
        )

    def retention(self) -> dict[str, Any]:
        """Run configured audit and disk-log retention under the fixed worker identity."""
        return self._runtime.execute(
            "maintenance.retention",
            ("app.maintenance:run",),
            lambda actor, sample: self._services.retention(),
        )

    def refresh_public_oncokb(self) -> dict[str, Any]:
        """Refresh public OncoKB gene records from the local HGNC catalog."""
        return self._runtime.execute(
            "maintenance.refresh_public_oncokb",
            ("app.maintenance:run",),
            lambda actor, sample: self._services.oncokb(),
        )

    def refresh_dashboard(
        self,
        *,
        username: str | None = None,
        metrics: list[str] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Refresh unique metric scopes for current active account records.

        Args:
            username: Optional stored username; None refreshes all active account scopes.
            metrics: Registered metric keys; None or an empty list selects every key.
                Existing scheduled-job behavior ignores unknown keys.
            task_id: Host task correlation identifier for failure logs; None omits it.

        Returns:
            Refreshed/skipped counts and safe per-account/per-metric failure categories.

        Raises:
            AppError: The host identity lacks the maintenance execution capability.

        Notes:
            The host owns the cross-process refresh lock. A scope is refreshed once per
            operation and its refresh lock is released after success or metric failure.
        """

        def refresh(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Resolve current scopes and retain independent failure handling per metric."""
            service = self._services.dashboard()
            user_docs = self._services.users()
            eligible = [
                doc
                for doc in user_docs
                if doc.get("is_active") is not False
                and (not username or str(doc.get("username") or doc.get("_id") or "") == username)
            ]
            selected = sorted(set(metrics or DASHBOARD_METRICS) & DASHBOARD_METRICS)
            refreshed, skipped = 0, len(user_docs) - len(eligible)
            failures: list[dict[str, str]] = []
            completed: set[tuple[str, str]] = set()
            for document in eligible:
                stored_username = str(document.get("username") or document.get("_id") or "")
                try:
                    user = self._services.identity(document)
                except Exception as exc:
                    self._services.logger.exception(
                        "celery_dashboard_metrics_user_failed task_id=%s username=%s",
                        task_id,
                        stored_username,
                    )
                    failures.append({"username": stored_username, "error": type(exc).__name__})
                    continue
                for metric in selected:
                    key = (metric, service.metric_scope_key(metric, user=user))
                    if key in completed:
                        skipped += 1
                        continue
                    try:
                        service.metric_payload(metric, user=user, force=True)
                        completed.add(key)
                        refreshed += 1
                    except Exception as exc:
                        self._services.logger.exception(
                            "celery_dashboard_metric_refresh_failed task_id=%s username=%s metric=%s",
                            task_id,
                            stored_username,
                            metric,
                        )
                        failures.append(
                            {
                                "username": stored_username,
                                "metric": metric,
                                "error": type(exc).__name__,
                            }
                        )
                    finally:
                        service.release_metric_refresh(metric, user=user)
            return {
                "status": "completed" if not failures else "completed_with_errors",
                "refreshed": refreshed,
                "skipped": skipped,
                "failures": failures,
            }

        return self._runtime.execute(
            "maintenance.refresh_dashboard", ("app.maintenance:run",), refresh
        )
