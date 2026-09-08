"""Non-production environments are visible in both OpenAPI documentation viewers."""

import pytest

from api.app.main import create_api_app


@pytest.mark.parametrize("environment", ["development", "staging", "test", "validation"])
def test_nonproduction_openapi_warning(monkeypatch, environment):
    monkeypatch.setenv("ENV_NAME", environment)
    schema = create_api_app().openapi()
    assert f"WARNING: {environment.upper()} environment" in schema["info"]["description"]


@pytest.mark.parametrize("environment", ["production", "prod"])
def test_production_openapi_has_no_warning(monkeypatch, environment):
    monkeypatch.setenv("ENV_NAME", environment)
    description = create_api_app().openapi()["info"]["description"]
    assert "WARNING:" not in description
    assert "## Authentication" in description
