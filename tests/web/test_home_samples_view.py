"""Samples home view behavior tests."""

from __future__ import annotations

import importlib

from flask import Flask


def test_samples_home_uses_query_tab_and_pagination(monkeypatch):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WTF_CSRF_ENABLED=False)
    app.home_logger = app.logger
    with app.app_context():
        views_samples = importlib.import_module("coyote.blueprints.home.views_samples")

        captured: dict = {}

        def _fetch_samples(**kwargs):
            captured.update(kwargs)
            return {
                "live_samples": [{"name": "S1"}],
                "done_samples": [],
                "sample_view": kwargs["sample_view"],
                "page": kwargs["page"],
                "per_page": kwargs["per_page"],
                "has_next_live": True,
                "has_next_done": False,
            }

        def _render(_template_name, **context):
            return context

        monkeypatch.setattr(views_samples, "fetch_samples", _fetch_samples)
        monkeypatch.setattr(views_samples, "render_template", _render)

        with app.test_request_context("/samples/live?view=reported&page=2&per_page=15", method="GET"):
            context = views_samples.samples_home.__wrapped__("live")

        assert captured["sample_view"] == "reported"
        assert captured["page"] == 2
        assert captured["per_page"] == 15
        assert context["sample_view"] == "reported"
        assert context["page"] == 2
        assert context["has_next_live"] is True


def test_samples_template_contains_tab_filters():
    template_path = "coyote/blueprints/home/templates/samples_home.html"
    with open(template_path, encoding="utf-8") as handle:
        html = handle.read()

    assert "view='live'" in html
    assert "view='reported'" in html
    assert "view='all'" in html
    assert 'name="view"' in html
