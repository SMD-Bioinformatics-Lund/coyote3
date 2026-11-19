"""Presentation must preserve API contracts, deployment prefixes and data boundaries."""

import re

import pytest
from coyote_api.app.documentation import register_api_documentation
from coyote_api.app.main import create_api_app
from coyote_api.interfaces.http.tags import OPENAPI_TAG_NAMES
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from starlette.requests import Request


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/docs", "/api/v1/redoc"])
@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("relay_installed", [False, True])
async def test_documentation_preserves_prefix_and_security(
    path, environment, relay_installed, monkeypatch
):
    """Mounted viewers use local routes and avoid retaining credentials in the browser."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/api/v1/openapi.json")
    monkeypatch.setattr("coyote_api.app.documentation.APPLICATION_VERSION", "4.2.1")
    app.version = "1.3.2"
    app.state.api_extensions = ("relay",) if relay_installed else ()
    register_api_documentation(app, environment=environment)
    route = next(route for route in app.routes if route.path == path)
    response = await route.endpoint(Request({"type": "http", "root_path": "/center", "path": path}))
    html = response.body.decode()
    assert 'href="/center/api/v1/redoc"' in html
    assert 'href="/center/api/v1/docs"' in html
    assert 'href="/center/docs-site/"' in html
    assert 'const schemaUrl = "/center/api/v1/openapi.json"' in html
    assert ('class="environment-warning"' in html) is (environment != "production")
    assert response.headers["Cache-Control"] == "no-store"
    assert "validatorUrl: null" in html
    assert "persistAuthorization: false" in html
    assert "disableGoogleFont: true" in html
    stored_keys = re.findall(r'localStorage\.setItem\("([^"]+)"', html)
    assert stored_keys == ["coyote4-docs-theme"]
    assert html.count("localStorage.setItem(") == len(stored_keys)
    assert "sessionStorage" not in html
    assert "OpenAPI " + app.openapi_version in html
    assert "Application v4.2.1" in html
    assert "Server v1.3.2" in html
    if path.endswith("redoc"):
        assert "https://YOUR_HOST/center/api/v1/auth/whoami" in html
        assert ("X-Coyote-Ingest-Token" in html) is relay_installed
    else:
        assert 'href="/center/docs-site/api/authentication/"' in html
        assert (
            'href="/center/docs-site/api/sample-ingestion/#managed-service-credentials"' in html
        ) is relay_installed
    assert 'href="/center/docs-site/administration/document-editing/"' in html


@pytest.mark.asyncio
async def test_documentation_escapes_labels_and_script_urls():
    app = FastAPI(docs_url=None, redoc_url=None)
    app.version = '<script>alert("version")</script>'
    register_api_documentation(app, environment='<img src=x onerror="alert(1)">')
    route = next(route for route in app.routes if route.path == "/api/v1/redoc")
    response = await route.endpoint(Request({"type": "http", "root_path": "/</script>"}))
    html = response.body.decode()
    assert '<script>alert("version")</script>' not in html
    assert '<img src=x onerror="alert(1)">' not in html
    assert 'const schemaUrl = "/</script>' not in html
    assert "\\u003c/script\\u003e" in html


def test_documentation_groups_include_every_tag_once(monkeypatch):
    monkeypatch.setenv("ENV_NAME", "test")
    app = create_api_app()
    schema = app.openapi()
    grouped = [tag for group in schema["x-tagGroups"] for tag in group["tags"]]
    assert sorted(grouped) == sorted(OPENAPI_TAG_NAMES)
    assert "/api/v1/docs" not in schema["paths"]
    assert "/api/v1/redoc" not in schema["paths"]
    assert schema["servers"] == [{"url": app.root_path or "/"}]
    assert schema["paths"]["/api/v1/samples"]["get"]["security"]
    logout_security = schema["paths"]["/api/v1/auth/sessions/current"]["delete"]["security"]
    assert {"BearerAuth": []} in logout_security
    assert {"ApiSessionCookie": []} in logout_security
    assert {} in logout_security  # Anonymous logout remains a supported no-op.
    assert not schema["paths"]["/api/v1/auth/sessions"]["post"].get("security")
    sync_security = schema["paths"]["/api/v1/internal/ingest/sample-bundle/upload"]["post"][
        "security"
    ]
    assert {"IngestToken": []} in sync_security
    async_security = schema["paths"]["/api/v1/internal/ingest/sample-bundle/upload/async"]["post"][
        "security"
    ]
    assert {"IngestToken": []} not in async_security
    routes = list(iter_route_contexts(app.routes))
    assert any(route.path == "/api/v1/health" for route in routes)
    assert "/api/v1/internal/ingest/collection" in schema["paths"]
    assert "/api/v1/internal/ingest/collections" in schema["paths"]
    assert "/api/v1/internal/metrics" not in schema["paths"]
