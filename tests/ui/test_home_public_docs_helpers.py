"""Coverage tests for home/public filters and docs helpers."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound


def _load_home_filters():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        return importlib.import_module("coyote.blueprints.home.filters"), app


def _load_public_filters():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        return importlib.import_module("coyote.blueprints.public.filters")


def _load_docs_views_common():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        return importlib.import_module("coyote.blueprints.docs.views_common")


def test_home_filters_file_state_and_markdown(tmp_path: Path):
    """Cover file state/human size/markdown helpers."""
    filters, _app = _load_home_filters()

    p = tmp_path / "sample.txt"
    p.write_text("hello", encoding="utf-8")
    assert filters.file_state(str(p)) is True
    assert filters.file_state([str(p)]) is True
    assert filters.file_state("N/A") is False
    assert filters.file_state(None) is False

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert filters.human_filesize(str(empty)) == "Empty"
    assert "B" in filters.human_filesize(str(p))
    assert filters.human_filesize(str(tmp_path / "missing.txt")) == "Not Available"

    rendered = str(filters.render_markdown("**hello**"))
    assert "hello" in rendered


def test_home_filters_isgl_meta_with_cache_and_fallback(monkeypatch):
    """Cover ISGL metadata filters and error fallback paths."""
    filters, app = _load_home_filters()
    calls = {"count": 0}

    class _Client:
        def get_json(self, _path, headers=None):  # noqa: ARG002
            calls["count"] += 1
            return SimpleNamespace(is_adhoc=True, display_name="My ISGL")

    with app.test_request_context("/"):
        monkeypatch.setattr(filters, "get_web_api_client", lambda: _Client())
        monkeypatch.setattr(filters, "build_internal_headers", lambda: {"X": "1"})
        monkeypatch.setattr(filters.api_endpoints, "internal", lambda *parts: "/".join(parts))

        assert filters.isgl_adhoc_status("GL1") is True
        assert filters.isgl_display_name("GL1") == "My ISGL"
        # Cache hit should avoid extra API call.
        assert filters.isgl_display_name("GL1") == "My ISGL"
        assert calls["count"] == 1

    with app.test_request_context("/"):

        class _ErrClient:
            def get_json(self, _path, headers=None):  # noqa: ARG002
                raise filters.ApiRequestError("boom")

        monkeypatch.setattr(filters, "get_web_api_client", lambda: _ErrClient())
        assert filters.isgl_adhoc_status("GL2") is False
        assert filters.isgl_display_name("GL2") == "GL2"


def test_public_filters_render_badges(monkeypatch):
    """Cover public input material badge formatting."""
    filters = _load_public_filters()
    monkeypatch.setattr(filters.random, "choice", lambda seq: seq[0])

    assert filters.get_color({"dna": "bg-green-600"}, "dna") == "bg-green-600"
    # Unknown key uses random fallback.
    assert filters.get_color({}, "unknown").startswith("bg-")

    html = filters.format_input_material(["DNA", "bone marrow", "unknown"])
    assert "bg-green-600" in html
    assert "bg-yellow-600" in html
    assert "unknown" in html


def test_docs_helpers_render_and_search(tmp_path: Path, monkeypatch):
    """Cover docs markdown rendering and search ranking/filtering."""
    views_common = _load_docs_views_common()

    md = tmp_path / "doc.md"
    md.write_text(
        "# Title\n\nhello [x](https://example.com)\n\n<script>alert(1)</script>", encoding="utf-8"
    )
    html = views_common.render_markdown_file(md)
    assert "Title" in html
    assert "href=" in html
    assert "<script>" not in html

    with pytest.raises(NotFound):
        views_common.render_markdown_file(tmp_path / "missing.md")

    # Build synthetic docs tree.
    base = tmp_path / "a"
    docs = base / "docs"
    (docs / "user").mkdir(parents=True, exist_ok=True)
    (docs / "developer").mkdir(parents=True, exist_ok=True)
    (docs / "admin").mkdir(parents=True, exist_ok=True)
    (docs / "user" / "quick-start.md").write_text(
        "# Quick Start\nalpha beta gamma", encoding="utf-8"
    )
    (docs / "developer" / "deep-dive.md").write_text(
        "# Deep Dive\nalpha internals", encoding="utf-8"
    )
    (docs / "admin" / "ops.md").write_text("# Ops\nalpha ops", encoding="utf-8")

    # Make docs_root resolve to our synthetic tree via __file__.parents[3] / "docs".
    monkeypatch.setattr(views_common, "__file__", str(base / "x" / "y" / "z" / "views_common.py"))

    # Permission helper branches.
    monkeypatch.setattr(
        views_common,
        "current_user",
        SimpleNamespace(
            is_authenticated=False,
            has_permission=lambda _p: False,
            has_min_access_level=lambda _l: False,
        ),
    )
    assert views_common.can_view_developer_docs() is False
    results = views_common.search_handbook_docs("alpha")
    assert all(not item["doc_path"].startswith("developer/") for item in results)
    assert all(not item["doc_path"].startswith("admin/") for item in results)

    monkeypatch.setattr(
        views_common,
        "current_user",
        SimpleNamespace(
            is_authenticated=True,
            has_permission=lambda _p: True,
            has_min_access_level=lambda _l: False,
        ),
    )
    assert views_common.can_view_developer_docs() is True
    results = views_common.search_handbook_docs("alpha")
    assert any(item["doc_path"].startswith("developer/") for item in results)
