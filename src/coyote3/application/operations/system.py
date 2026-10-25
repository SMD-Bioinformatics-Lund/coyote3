"""Application operations for dashboards, controls, installation and traceability."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from coyote3.application.dashboard.cache import DASHBOARD_METRICS
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.admin.app_controls import AppControlsService
    from coyote3.application.audit.service import AuditService
    from coyote3.application.dashboard.analytics import DashboardService


class OperationsServices:
    """Host-owned operational integrations; application operations do not import workers."""

    def __init__(
        self,
        *,
        dashboard: Callable[[], DashboardService],
        controls: Callable[[], AppControlsService],
        audit: Callable[[], AuditService],
        enqueue: Callable[[str, dict[str, Any]], str],
        issue_token: Callable[[Any, int], dict[str, Any]],
        schemas: Mapping[str, Any],
    ) -> None:
        """Bind service factories, task submission, credential issuance and schema contracts.

        Args:
            dashboard: Scoped metric and refresh-lock implementation.
            controls: Effective configuration and persisted override implementation.
            audit: Durable event reader.
            enqueue: Publishes an allowlisted operational task and returns its identifier.
            issue_token: Issues and audits a credential for the verified actor and hours.
            schemas: Authoritative collection contract adapters used for inspection.
        """
        self.dashboard, self.controls = dashboard, controls
        self.audit = audit
        self.enqueue, self.issue_token, self.schemas = enqueue, issue_token, schemas


class Dashboard:
    """Read scoped metrics and request refreshes under the current identity."""

    def __init__(self, runtime: ApplicationRuntime, services: OperationsServices) -> None:
        """Bind the authorization runtime, metric service and background task port."""
        self._runtime, self._services = runtime, services

    def metric(self, metric: str) -> dict[str, Any]:
        """Read a named metric, queueing a refresh when stale and unlocked.

        Args:
            metric: One of the registered DASHBOARD_METRICS keys.

        Returns:
            Current cached metric and cache metadata for the authenticated actor's scope.

        Raises:
            AppError: Authentication fails or the metric key is unknown.
        """

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Use the same actor for metric visibility and refresh-lock ownership."""
            self._validate([metric])
            service = self._services.dashboard()
            payload = service.metric_payload(metric, user=actor)
            if payload.get("metric_meta", {}).get("stale") and service.acquire_metric_refresh(
                metric, user=actor
            ):
                self._services.enqueue(
                    "dashboard", {"username": actor.username, "metrics": [metric]}
                )
            return dict(payload)

        return self._runtime.execute("dashboard.metric", None, read)

    @staticmethod
    def _validate(metrics: list[str]) -> None:
        """Reject unknown metric keys before queue submission."""
        unknown = sorted(set(metrics) - DASHBOARD_METRICS)
        if unknown:
            raise api_error(422, f"Unknown dashboard metrics: {', '.join(unknown)}")

    def refresh(self, metrics: list[str] | None = None) -> dict[str, Any]:
        """Queue selected metrics for the current user's scope.

        Args:
            metrics: Registered keys; None or an empty list refreshes every metric.

        Returns:
            Queued status and the submitted task identifier.

        Raises:
            AppError: Authentication fails or a selected metric is unknown.
        """

        def submit(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Validate keys before publishing the actor-attributed task."""
            selected = metrics or sorted(DASHBOARD_METRICS)
            self._validate(selected)
            return {
                "status": "queued",
                "task_id": self._services.enqueue(
                    "dashboard", {"username": actor.username, "metrics": selected}
                ),
            }

        return self._runtime.execute("dashboard.refresh", None, submit)

    def admin_insights(self) -> dict[str, Any]:
        """Read administrative insights with dashboard.admin:view permission."""
        return self._runtime.execute(
            "dashboard.admin_insights",
            ("dashboard.admin:view",),
            lambda actor, sample: dict(self._services.dashboard().build_admin_insights()),
        )


class Controls:
    """Inspect and change runtime controls and queue explicit maintenance operations."""

    def __init__(self, runtime: ApplicationRuntime, services: OperationsServices) -> None:
        """Bind authorization, control persistence and maintenance submission."""
        self._runtime, self._services = runtime, services

    def read(self) -> dict[str, Any]:
        """Read effective runtime controls with app.controls:view permission."""
        return self._runtime.execute(
            "controls.read",
            ("app.controls:view",),
            lambda actor, sample: dict(self._services.controls().payload()),
        )

    def update(self, controls: dict[str, Any]) -> dict[str, Any]:
        """Persist control overrides and return their effective values.

        Args:
            controls: Supported runtime control overrides validated by the control service.

        Returns:
            Effective control values after the actor-attributed update.

        Raises:
            AppError: app.controls:edit is denied or overrides fail validation.
        """

        def save(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Apply overrides before reloading effective control values."""
            service = self._services.controls()
            service.update_controls(controls, actor=actor)
            return dict(service.payload())

        return self._runtime.execute("controls.update", ("app.controls:edit",), save)

    def maintenance(self) -> dict[str, Any]:
        """Queue retention cleanup with app.maintenance:run permission."""
        return self._runtime.execute(
            "controls.maintenance",
            ("app.maintenance:run",),
            lambda actor, sample: {
                "status": "queued",
                "task_id": self._services.enqueue("retention", {}),
            },
        )

    def refresh_public_oncokb(self) -> dict[str, Any]:
        """Queue HGNC-backed public OncoKB refresh with app.maintenance:run permission."""
        return self._runtime.execute(
            "controls.refresh_public_oncokb",
            ("app.maintenance:run",),
            lambda actor, sample: {
                "status": "queued",
                "task_id": self._services.enqueue("oncokb", {}),
            },
        )


class Traceability:
    """Read durable audit records and inspect the authoritative collection schemas."""

    def __init__(self, runtime: ApplicationRuntime, services: OperationsServices) -> None:
        """Bind current grants, audit storage and schema adapters."""
        self._runtime, self._services = runtime, services

    def events(self, limit: int = 200) -> dict[str, Any]:
        """Read recent durable audit events with audit_log:view permission.

        Args:
            limit: Maximum recent events, from 1 to 1000; defaults to 200.

        Returns:
            Existing durable audit event envelope.

        Raises:
            AppError: Permission is denied or the requested limit is outside its bounds.
        """

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Check the public limit before querying the traceability store."""
            if not 1 <= limit <= 1000:
                raise api_error(422, "Audit event limit must be between 1 and 1000")
            return dict(self._services.audit().recent_events(limit=limit))

        return self._runtime.execute("traceability.events", ("audit_log:view",), read)

    def schemas(self, q: str = "") -> dict[str, Any]:
        """Inspect registered collection contracts with schema:list permission.

        Args:
            q: Case-insensitive collection-name search; empty text selects every schema.

        Returns:
            Schema definitions, required keys, property names and total count.
        """

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Build schema descriptions from the authoritative registered adapters."""
            needle = q.strip().lower()
            rows = []
            for collection, adapter in sorted(self._services.schemas.items()):
                if needle and needle not in collection.lower():
                    continue
                try:
                    schema = adapter.json_schema()
                except Exception:
                    schema = {}
                rows.append(
                    {
                        "collection": collection,
                        "title": schema.get("title") or collection,
                        "required": schema.get("required") or [],
                        "properties": sorted((schema.get("properties") or {}).keys()),
                        "schema": schema,
                    }
                )
            return {"schemas": rows, "total": len(rows)}

        return self._runtime.execute("traceability.schemas", ("schema:list",), read)


class Credentials:
    """Issue fixed-audience ingestion credentials for an authorized current identity."""

    def __init__(self, runtime: ApplicationRuntime, services: OperationsServices) -> None:
        """Bind permission checks and the host's audited credential issuer."""
        self._runtime, self._services = runtime, services

    def issue_ingest_token(self, hours: int) -> dict[str, Any]:
        """Issue and audit an expiring ingestion credential with ingest.token:issue.

        Args:
            hours: Requested lifetime accepted by the existing credential issuer.

        Returns:
            Credential and expiry metadata; callers must store the credential securely.

        Raises:
            AppError: Permission is denied or credential issuance is unavailable.
        """

        def issue(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Translate unavailable signing infrastructure to the established application error."""
            try:
                return self._services.issue_token(actor, hours)
            except RuntimeError:
                raise api_error(503, "Token issuance is unavailable") from None

        return self._runtime.execute(
            "credentials.issue_ingest_token", ("ingest.token:issue",), issue
        )
