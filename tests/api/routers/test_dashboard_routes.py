"""Behavior tests for dashboard API routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.interfaces.http.v1.operations import dashboard
from api.tasks import maintenance
from coyote3.application.operations import system as sdk_operations
from coyote3.contracts.dashboard import DashboardMetricRefreshRequest
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


@pytest.mark.parametrize(
    ("route", "metric"),
    [
        (dashboard.dashboard_sample_metrics, "samples"),
        (dashboard.dashboard_finding_metrics, "findings"),
        (dashboard.dashboard_top_tiered_gene_metrics, "top_tiered_genes"),
        (dashboard.dashboard_panel_metrics, "panels"),
        (dashboard.dashboard_clinical_configuration_metrics, "clinical_configuration"),
        (dashboard.dashboard_resource_metrics, "resources"),
    ],
)
def test_dashboard_metric_routes_return_only_the_requested_metric(monkeypatch, route, metric):
    calls: list[str] = []
    service = SimpleNamespace(
        metric_payload=lambda requested, *, user: (
            calls.append(requested)
            or {
                "value": 3,
                "metric_meta": {
                    "metric": requested,
                    "generated_at": "2026-09-03T10:00:00Z",
                    "cache_hit": True,
                    "stale": False,
                },
            }
        ),
        acquire_metric_refresh=lambda requested, *, user: False,
    )

    payload = route(
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_operations.Dashboard, service, fx.api_user()
        ),
    )

    assert calls == [metric]
    assert payload["metric_meta"]["metric"] == metric
    assert payload["value"] == 3


def test_stale_metric_is_returned_and_queues_its_own_refresh(monkeypatch):
    queued: list[tuple[str, list[str]]] = []
    user = fx.api_user()
    service = SimpleNamespace(
        metric_payload=lambda requested, *, user: {
            "value": 7,
            "metric_meta": {
                "metric": requested,
                "generated_at": "2026-09-03T09:00:00Z",
                "cache_hit": True,
                "stale": True,
            },
        },
        acquire_metric_refresh=lambda requested, *, user: True,
    )
    monkeypatch.setattr(
        maintenance.refresh_dashboard_metrics,
        "delay",
        lambda *, username, metrics: (
            queued.append((username, metrics)) or SimpleNamespace(id="refresh-task")
        ),
    )

    payload = sdk_fixtures.invoke_route(
        dashboard.dashboard_finding_metrics,
        user=user,
        service=sdk_fixtures.authorized_operations(sdk_operations.Dashboard, service, user),
    )

    assert payload["value"] == 7
    assert queued == [(user.username, ["findings"])]


def test_fresh_metric_does_not_queue_refresh(monkeypatch):
    service = SimpleNamespace(
        metric_payload=lambda requested, *, user: {
            "metric_meta": {"metric": requested, "stale": False}
        },
        acquire_metric_refresh=lambda requested, *, user: pytest.fail(
            "a fresh metric must not acquire a refresh lock"
        ),
    )
    monkeypatch.setattr(
        maintenance.refresh_dashboard_metrics,
        "delay",
        lambda **_kwargs: pytest.fail("a fresh metric must not queue work"),
    )

    sdk_fixtures.invoke_route(
        dashboard.dashboard_sample_metrics,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_operations.Dashboard, service, fx.api_user()
        ),
    )


def test_dashboard_refresh_queues_selected_metrics(monkeypatch):
    queued: list[tuple[str, list[str]]] = []

    class _Result:
        id = "dashboard-task-1"

    monkeypatch.setattr(
        maintenance.refresh_dashboard_metrics,
        "delay",
        lambda *, username, metrics: queued.append((username, metrics)) or _Result(),
    )
    user = fx.api_user()

    payload = sdk_fixtures.invoke_route(
        dashboard.refresh_dashboard_metric_cache,
        DashboardMetricRefreshRequest(metrics=["samples", "findings"]),
        user=user,
        service=sdk_fixtures.authorized_operations(sdk_operations.Dashboard, None, user),
    )

    assert payload == {"status": "queued", "task_id": "dashboard-task-1"}
    assert queued == [(user.username, ["samples", "findings"])]


def test_dashboard_refresh_rejects_unknown_metric():
    with pytest.raises(AppError) as exc_info:
        sdk_fixtures.invoke_route(
            dashboard.refresh_dashboard_metric_cache,
            DashboardMetricRefreshRequest(metrics=["not_a_metric"]),
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_operations.Dashboard, None, fx.api_user()
            ),
        )

    assert exc_info.value.status_code == 422
    assert "not_a_metric" in str(exc_info.value.detail)


def test_dashboard_admin_insights_returns_service_payload(monkeypatch):
    service = SimpleNamespace(build_admin_insights=lambda: {"counts": {"users_total": 12}})

    payload = sdk_fixtures.invoke_route(
        dashboard.dashboard_admin_insights,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_operations.Dashboard, service, fx.api_user()
        ),
    )

    assert payload == {"counts": {"users_total": 12}}
