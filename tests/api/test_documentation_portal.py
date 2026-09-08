"""Presentation must preserve API contracts, deployment prefixes and data boundaries."""

import re
import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from starlette.requests import Request

from api.app.documentation import register_api_documentation
from api.app.main import create_api_app
from api.interfaces.http.tags import OPENAPI_TAG_NAMES


def test_documentation_colors_match_application_light_theme():
    application = Path("frontend/src/styles/tailwind-theme.css").read_text()
    documentation = Path("api/app/templates/api_reference.css").read_text()
    names = (
        "background",
        "foreground",
        "card",
        "primary",
        "muted-foreground",
        "border",
        "brand-start",
        "brand-end",
        "brand-gradient",
        "chrome-top",
        "chrome-foreground",
        "chrome-muted-foreground",
        "chrome-border",
        "chrome-control-hover",
        "status-warning-soft",
        "status-warning-foreground",
    )
    for name in names:
        pattern = rf"--{re.escape(name)}:\s*([^;]+);"
        expected = re.search(pattern, application)
        actual = re.search(pattern, documentation)
        assert expected and actual, f"Missing brand token: {name}"
        assert " ".join(actual[1].split()) == " ".join(expected[1].split()), name


def test_documentation_assets_are_included_in_python_packages():
    config = tomllib.loads(Path("pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["api"]
    packaged = {path for pattern in patterns for path in Path("api").glob(pattern)}
    assets = set(Path("api/app/templates").glob("*"))
    assert assets and assets <= packaged


def test_response_samples_use_application_dark_theme_tokens():
    application = Path("frontend/src/styles/tailwind-theme.css").read_text()
    documentation = Path("api/app/templates/api_reference.css").read_text()
    for target, source in {
        "code-surface": "card",
        "code-ink": "foreground",
        "code-string": "primary",
        "code-success": "status-success-foreground",
    }.items():
        expected = re.findall(rf"--{source}:\s*([^;]+);", application)[-1]
        actual = re.search(rf"--{target}:\s*([^;]+);", documentation)
        assert actual and actual[1] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/docs", "/api/v1/redoc"])
@pytest.mark.parametrize("environment", ["production", "staging"])
async def test_documentation_branding_prefix_and_environment(path, environment):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/api/v1/openapi.json")
    register_api_documentation(app, environment=environment)
    route = next(route for route in app.routes if route.path == path)
    response = await route.endpoint(Request({"type": "http", "root_path": "/center", "path": path}))
    html = response.body.decode()
    assert "Coyote3 API" in html
    assert 'href="/center/api/v1/redoc"' in html
    assert 'href="/center/api/v1/docs"' in html
    assert 'href="/center/docs-site/"' in html
    assert 'const schemaUrl = "/center/api/v1/openapi.json"' in html
    assert "data:image/png;base64," in html
    assert ('class="environment-warning"' in html) is (environment != "production")
    assert response.headers["Cache-Control"] == "no-store"
    assert "validatorUrl: null" in html
    assert "persistAuthorization: false" in html
    assert "disableGoogleFont: true" in html
    assert "localStorage" not in html


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
    routes = list(iter_route_contexts(app.routes))
    assert any(route.path == "/api/v1/health" for route in routes)
    assert not any(path.startswith("/api/v1/internal/") for path in schema["paths"])
