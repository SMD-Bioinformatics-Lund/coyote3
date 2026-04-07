"""Regression tests for extracted shared and coverage page scripts."""

from __future__ import annotations

from pathlib import Path

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from tests.ui.test_ui_additional_route_flows import _fixture_shaped_get


def test_shared_footer_uses_layout_asset():
    """The shared footer should load the extracted layout script asset."""
    template = Path("coyote/templates/_partials/_footer.html").read_text()

    assert "js/layout.js" in template
    assert "<script>" not in template


def test_coverage_template_uses_blueprint_asset_without_inline_logic():
    """Coverage template should delegate its behavior to the blueprint JS asset."""
    template = Path("coyote/blueprints/coverage/templates/show_cov.html").read_text()

    assert "cov_bp.static" in template
    assert "js/show_cov.js" in template
    assert 'data-plot-gene="' in template
    assert 'onclick="plotGene' not in template
    assert "<script>" not in template


def test_coverage_page_renders_extracted_script_assets(monkeypatch):
    """Coverage page should render with the shared and blueprint-local script assets."""

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        return _fixture_shaped_get(path)

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)

    app = init_app(testing=True)
    client = app.test_client()

    response = client.get("/cov/s1")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "js/layout.js?v=" in body
    assert "js/show_cov.js?v=" in body
