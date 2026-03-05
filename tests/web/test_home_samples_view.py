"""Samples home view behavior tests."""

from __future__ import annotations

import importlib

from flask import Flask


def test_samples_home_uses_table_specific_pagination_and_profile_scope(monkeypatch):
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
                "sample_view": "all",
                "profile_scope": kwargs["profile_scope"],
                "page": kwargs["page"],
                "per_page": kwargs["per_page"],
                "live_page": kwargs["live_page"],
                "done_page": kwargs["done_page"],
                "live_per_page": kwargs["live_per_page"],
                "done_per_page": kwargs["done_per_page"],
                "has_next_live": True,
                "has_next_done": False,
            }

        def _render(_template_name, **context):
            return context

        monkeypatch.setattr(views_samples, "fetch_samples", _fetch_samples)
        monkeypatch.setattr(views_samples, "render_template", _render)

        with app.test_request_context(
            "/samples/live?view=reported&lp=2&dp=3&lpp=15&dpp=25&scope=all&q=ABC",
            method="GET",
        ):
            context = views_samples.samples_home.__wrapped__("live")

        assert captured["sample_view"] == "reported"
        assert captured["live_page"] == 2
        assert captured["done_page"] == 3
        assert captured["live_per_page"] == 15
        assert captured["done_per_page"] == 25
        assert captured["profile_scope"] == "all"
        assert captured["search_str"] == "ABC"
        assert context["sample_view"] == "all"
        assert context["live_page"] == 2
        assert context["done_page"] == 3
        assert context["has_next_live"] is True


def test_samples_template_contains_tab_filters():
    template_path = "coyote/blueprints/home/templates/samples_home.html"
    with open(template_path, encoding="utf-8") as handle:
        html = handle.read()

    assert "scope='all'" in html
    assert 'name="q"' in html
