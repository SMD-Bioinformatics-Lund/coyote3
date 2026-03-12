"""Startup-path tests for the canonical API entrypoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_canonical_api_entrypoint_serves_health():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
