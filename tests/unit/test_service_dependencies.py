"""Dependency-provider wiring at the application composition boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.app.deps import services


@pytest.fixture(autouse=True)
def clear_provider_caches() -> None:
    """Keep cached dependency providers isolated between tests."""
    for value in vars(services).values():
        cache_clear = getattr(value, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


@pytest.mark.parametrize(
    ("provider_name", "service_name"),
    [
        ("get_admin_user_service", "UserManagementService"),
        ("get_admin_role_service", "RoleManagementService"),
        ("get_permission_management_service", "PermissionManagementService"),
        ("get_admin_panel_service", "AspService"),
        ("get_admin_genelist_service", "IsglService"),
        ("get_admin_aspc_service", "AspcService"),
        ("get_admin_sample_service", "ResourceSampleService"),
        ("get_coverage_service", "CoverageService"),
        ("get_dashboard_service", "DashboardService"),
        ("get_dna_service", "DnaService"),
        ("get_biomarker_service", "BiomarkerService"),
        ("get_classification_service", "ResourceClassificationService"),
        ("get_resource_annotation_service", "ResourceAnnotationService"),
        ("get_sample_catalog_service", "SampleCatalogService"),
        ("get_rna_service", "RnaService"),
        ("get_dna_structural_service", "DnaStructuralService"),
        ("get_user_service", "UserService"),
        ("get_common_query_service", "CommonQueryService"),
        ("get_sample_service", "SampleService"),
        ("get_public_catalog_service", "PublicCatalogService"),
        ("get_rna_workflow_service", "RNAWorkflowService"),
        ("get_dna_workflow_service", "DNAWorkflowService"),
        ("get_internal_ingest_service", "InternalIngestService"),
    ],
)
def test_store_backed_provider_builds_expected_service(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
    service_name: str,
) -> None:
    store = object()
    marker = object()
    factory = Mock(return_value=marker)
    monkeypatch.setattr(services, "get_store", lambda: store)
    monkeypatch.setattr(getattr(services, service_name), "from_store", factory)

    assert getattr(services, provider_name)() is marker
    assert factory.call_count == 1
    assert factory.call_args.args[0] is store


def test_report_service_provider_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = object()
    constructor = Mock(return_value=marker)
    monkeypatch.setattr(services, "ReportService", constructor)

    assert services.get_report_service() is marker
    assert services.get_report_service() is marker
    constructor.assert_called_once_with()


def test_api_session_repository_loads_only_active_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = {
        "active": {"username": "active", "is_active": True},
        "inactive": {"username": "inactive", "is_active": False},
    }
    store = SimpleNamespace(
        coyote_db={"sessions": object()},
        user_repository=SimpleNamespace(user_with_id=lambda username: users.get(username)),
    )
    captured: dict[str, object] = {}

    def repository(collection: object, **kwargs: object) -> object:
        captured.update(collection=collection, **kwargs)
        return captured

    monkeypatch.setattr(services, "get_store", lambda: store)
    monkeypatch.setattr(services, "get_api_sessions_collection_name", lambda config: "sessions")
    monkeypatch.setattr(services, "get_api_session_ttl_seconds", lambda config: 3600)
    monkeypatch.setattr(services, "MongoApiSessionRepository", repository)
    monkeypatch.setattr(
        "api.security.access.api_user_from_user_doc",
        lambda user: {"loaded": user["username"]},
    )

    assert services.get_api_session_repository() is captured
    loader = captured["user_loader"]
    assert callable(loader)
    assert loader("active") == {"loaded": "active"}
    assert loader("inactive") is None
    assert loader("missing") is None
    assert captured["ttl_seconds"] == 3600


def test_audit_service_requires_database_and_uses_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SimpleNamespace(coyote_db=None)
    monkeypatch.setattr(services, "get_store", lambda: store)
    assert services.get_audit_service() is None

    store.coyote_db = {"audit": object()}
    constructor = Mock(return_value="audit-service")
    monkeypatch.setattr(services, "AuditService", constructor)
    monkeypatch.setattr(services, "get_audit_events_collection_name", lambda config: "audit")
    monkeypatch.setattr(services, "effective_audit_retention_days", lambda db, config: 90)
    monkeypatch.setattr(services, "get_runtime_environment", lambda config: "testing")

    assert services.get_audit_service() == "audit-service"
    constructor.assert_called_once_with(
        store.coyote_db["audit"], retention_days=90, environment="testing"
    )


def test_notification_and_controls_providers_include_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SimpleNamespace(
        coyote_db=object(),
        _adapter=SimpleNamespace(index_setup_conflicts=[{"name": "conflict"}]),
    )
    monkeypatch.setattr(services, "get_store", lambda: store)
    monkeypatch.setattr(services, "get_audit_service", lambda: "audit")
    notification_factory = Mock(return_value="notifications")
    controls_factory = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(services.NotificationService, "from_store", notification_factory)
    monkeypatch.setattr(services, "AppControlsService", controls_factory)

    assert services.get_notification_service() == "notifications"
    assert services.get_app_controls_service() is controls_factory.return_value
    assert notification_factory.call_args.kwargs["audit_service"] == "audit"
    provider = controls_factory.call_args.kwargs["index_conflicts_provider"]
    assert provider() == [{"name": "conflict"}]
