"""Optional API routes reuse host authorization and require the reviewed bundle digest."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.domain.exceptions import AppError
from coyote_api.app.deps.services import get_deployment_data_service
from coyote_api.services.provisioning.deployment_data import DeploymentDataService
from coyote_atlas.api import routers
from coyote_atlas.api.routes import router
from coyote_atlas.bundle import ReferenceBundle
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.fixture
def host(monkeypatch):
    plan = ReferenceBundle.packaged().inspect()
    from coyote_atlas.models import InstallationPlan

    pinned = InstallationPlan(
        bundle_id=plan.bundle_id,
        bundle_version=plan.bundle_version,
        manifest_sha256="a" * 64,
        datasets=plan.datasets,
        collections={"hgnc_genes": 44084, "vep_metadata": 19, "vep_diagrams": 3},
    )
    bundle = Mock()
    bundle.plan.return_value = pinned
    monkeypatch.setattr(ReferenceBundle, "packaged", lambda: bundle)
    repository = Mock()
    repository.pending.return_value = ["hgnc_genes"]
    service = DeploymentDataService(repository, Mock())
    service.install = Mock(return_value={"collections": {"hgnc_genes": "loaded"}})
    user = SimpleNamespace(username="synthetic.admin", roles=["admin"], must_change_password=False)
    app = FastAPI()
    app.add_exception_handler(
        AppError, lambda request, exc: JSONResponse(status_code=exc.status_code, content=exc.detail)
    )
    for route in router.routes:
        app.dependency_overrides[route.dependant.dependencies[0].call] = lambda: user
    app.dependency_overrides[get_deployment_data_service] = lambda: service
    app.include_router(router)
    return SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False),
        user=user,
        service=service,
        bundle=bundle,
        repository=repository,
    )


def test_plugin_routes_are_installed():
    assert routers() == (router,)


def test_plan_is_read_only_and_discloses_validated_identity(host):
    response = host.client.get("/api/v1/admin/references/plan")
    assert response.status_code == 200
    assert response.json()["plan"]["manifest_sha256"] == "a" * 64
    assert response.json()["pending"] == ["hgnc_genes"]
    host.service.install.assert_not_called()


@pytest.mark.parametrize("force", [False, True])
def test_apply_reuses_authorized_installer_with_explicit_selection(host, force):
    response = host.client.post(
        "/api/v1/admin/references/apply",
        json={"expected_manifest_sha256": "a" * 64, "force": force},
    )
    assert response.status_code == 200
    host.service.install.assert_called_once_with(
        user=host.user, modules=["knowledgebase"], force=force
    )


def test_changed_plan_prevents_every_write(host):
    response = host.client.post(
        "/api/v1/admin/references/apply", json={"expected_manifest_sha256": "b" * 64}
    )
    assert response.status_code == 409
    host.service.install.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"expected_manifest_sha256": "invalid"},
        {"expected_manifest_sha256": "a" * 64, "path": "/tmp/custom"},
    ],
)
def test_request_rejects_missing_digest_and_caller_owned_resource_paths(host, body):
    assert host.client.post("/api/v1/admin/references/apply", json=body).status_code == 422
    host.service.install.assert_not_called()


@pytest.mark.parametrize("reason", ["role", "password", "username"])
@pytest.mark.parametrize("method,path", [("GET", "plan"), ("POST", "apply")])
def test_host_authorization_rejects_before_reference_or_target_access(host, reason, method, path):
    if reason == "role":
        host.user.roles = ["viewer"]
    elif reason == "password":
        host.user.must_change_password = True
    else:
        host.user.username = ""
    response = host.client.request(
        method,
        "/api/v1/admin/references/" + path,
        json={"expected_manifest_sha256": "a" * 64} if method == "POST" else None,
    )
    assert response.status_code == 403
    host.bundle.plan.assert_not_called()
    host.repository.pending.assert_not_called()
    host.service.install.assert_not_called()
