"""Contract exports reflect the real API without including deployment-specific metadata."""

from api.app.main import create_api_app
from scripts.contracts.export_openapi import export_schema


def test_export_preserves_server_routes_and_pydantic_contracts():
    original = create_api_app().openapi()
    exported = export_schema()
    assert exported["paths"] == original["paths"]
    assert exported["components"] == original["components"]
    assert "servers" not in exported
    assert exported["info"] == {"title": "Coyote3 API", "version": "1"}
