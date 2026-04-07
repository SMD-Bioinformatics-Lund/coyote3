"""UI regression tests for DNA page-level error rendering."""

from __future__ import annotations

import pytest

import coyote
from coyote import init_app


def _load_web_module(module_name: str):
    """Import a web module under an app context when it binds current_app at import time."""
    original_verify = coyote.verify_external_api_dependency
    coyote.verify_external_api_dependency = lambda _app: None
    try:
        app = init_app(testing=True)
    finally:
        coyote.verify_external_api_dependency = original_verify
    with app.app_context():
        module = __import__(module_name, fromlist=["unused"])
    return module


def test_cnv_and_translocation_detail_routes_raise_page_load_errors(monkeypatch):
    """CNV/translocation detail pages should use the standard page error flow."""
    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    views_cnv = _load_web_module("coyote.blueprints.dna.views_cnv")
    views_transloc = _load_web_module("coyote.blueprints.dna.views_transloc")

    class _FailingClient:
        def get_json(self, path, headers=None, params=None):  # noqa: ARG002
            raise views_cnv.ApiRequestError("boom", status_code=500)

    for module in (views_cnv, views_transloc):
        monkeypatch.setattr(module, "get_web_api_client", lambda: _FailingClient())
        monkeypatch.setattr(module, "forward_headers", lambda: {})

    cnv_calls: list[dict[str, str | None]] = []
    transloc_calls: list[dict[str, str | None]] = []

    def _raise_cnv(exc, *, logger, log_message, summary, not_found_summary=None):  # noqa: ARG001
        cnv_calls.append(
            {
                "log_message": log_message,
                "summary": summary,
                "not_found_summary": not_found_summary,
            }
        )
        raise RuntimeError("cnv-page-error")

    def _raise_transloc(exc, *, logger, log_message, summary, not_found_summary=None):  # noqa: ARG001
        transloc_calls.append(
            {
                "log_message": log_message,
                "summary": summary,
                "not_found_summary": not_found_summary,
            }
        )
        raise RuntimeError("transloc-page-error")

    monkeypatch.setattr(views_cnv, "raise_page_load_error", _raise_cnv)
    monkeypatch.setattr(views_transloc, "raise_page_load_error", _raise_transloc)

    app = init_app(testing=True)
    with app.app_context(), pytest.raises(RuntimeError, match="cnv-page-error"):
        views_cnv.show_cnv("S1", "cnv1")
    with app.app_context(), pytest.raises(RuntimeError, match="transloc-page-error"):
        views_transloc.show_transloc("S1", "tl1")

    assert cnv_calls[0]["summary"] == "Unable to load the CNV detail page."
    assert transloc_calls[0]["summary"] == "Unable to load the translocation detail page."


def test_cnv_route_renders_html_error_page_for_browser_requests(monkeypatch):
    """Browser requests to CNV detail should render the shared error page on upstream failure."""
    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    views_cnv = _load_web_module("coyote.blueprints.dna.views_cnv")

    class _FailingClient:
        def get_json(self, path, headers=None, params=None):  # noqa: ARG002
            raise views_cnv.ApiRequestError("boom", status_code=500)

    monkeypatch.setattr(views_cnv, "get_web_api_client", lambda: _FailingClient())
    monkeypatch.setattr(views_cnv, "forward_headers", lambda: {})

    app = init_app(testing=True)
    client = app.test_client()

    response = client.get("/dna/S1/cnv/cnv1", headers={"Accept": "text/html"})

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "Request Failed" in body
    assert "Unable to load the CNV detail page." in body
