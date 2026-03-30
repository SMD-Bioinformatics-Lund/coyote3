"""Additional high-yield tests for blueprint route helpers and RNA filters."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound


def _load_module(module_name: str):
    """Import module under Flask app context for current_app-proxy decorators."""
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    app.home_logger = app.logger
    with app.app_context():
        module = importlib.import_module(module_name)
    return module, app


def test_rna_filters_basic_helpers():
    """Cover RNA filter wrappers."""
    filters, _app = _load_module("coyote.blueprints.rna.filters")
    html = filters.format_fusion_desc_few("in-frame,driver", preview_count=1)
    assert "driver" in str(html) or "in-frame" in str(html)
    assert filters.format_fusion_desc("in-frame")
    assert filters.uniq_callers([{"caller": "A"}, {"caller": "A"}, {"caller": "B"}]) == {"A", "B"}


def test_public_misc_contact_reads_config(monkeypatch):
    """Cover public contact route rendering."""
    views_misc, app = _load_module("coyote.blueprints.public.views_misc")
    monkeypatch.setattr(
        views_misc,
        "render_template",
        lambda _template, **ctx: ctx,
    )
    app.config["CONTACT"] = {"email": "team@example.org"}
    with app.app_context():
        payload = views_misc.contact()
    assert payload["contact"]["email"] == "team@example.org"


def test_home_reports_serve_report_paths(tmp_path: Path, monkeypatch):
    """Cover report serving success and failure branches."""
    views_reports, app = _load_module("coyote.blueprints.home.views_reports")
    app.home_logger = app.logger

    report = tmp_path / "report.pdf"
    report.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(views_reports, "fetch_report_path", lambda _s, _r: report)
    monkeypatch.setattr(
        views_reports,
        "send_file",
        lambda path, as_attachment, download_name: {
            "name": Path(path).name,
            "as_attachment": as_attachment,
            "download_name": download_name,
        },
    )
    with app.app_context():
        rendered = views_reports._serve_report("S1", "R1", as_attachment=False)
    assert rendered["name"] == "report.pdf"
    assert rendered["as_attachment"] is False

    def _raise_page_load_error(*_args, **_kwargs):
        raise RuntimeError("page-load-error")

    monkeypatch.setattr(views_reports, "raise_page_load_error", _raise_page_load_error)
    monkeypatch.setattr(
        views_reports,
        "fetch_report_path",
        lambda _s, _r: (_ for _ in ()).throw(views_reports.ApiRequestError("boom")),
    )
    with app.app_context(), pytest.raises(RuntimeError, match="page-load-error"):
        views_reports._serve_report("S1", "R1", as_attachment=True)


def test_docs_meta_routes_about_changelog_license(tmp_path: Path, monkeypatch):
    """Cover docs metadata view logic."""
    views_meta, app = _load_module("coyote.blueprints.docs.views_meta")
    app.config.update(
        APP_NAME="Coyote3",
        APP_VERSION="4.0.0",
        ENV_NAME="test",
        CHANGELOG_FILE=str(tmp_path / "CHANGELOG.md"),
        LICENSE_FILE=str(tmp_path / "LICENSE.txt"),
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
    (tmp_path / "LICENSE.txt").write_text("MIT", encoding="utf-8")

    monkeypatch.setattr(views_meta, "render_template", lambda _template, **ctx: ctx)
    monkeypatch.setattr(views_meta, "render_markdown_file", lambda _path: "<h1>Changelog</h1>")

    with app.test_request_context("/"):
        about_payload = views_meta.about.__wrapped__()
        changelog_payload = views_meta.changelog.__wrapped__()
        license_payload = views_meta.license()

    assert about_payload["meta"]["app_version"] == "4.0.0"
    assert "Changelog" in changelog_payload["changelog_html"]
    assert "MIT" in license_payload["license_text"]

    app.config["CHANGELOG_FILE"] = ""
    with app.test_request_context("/"), pytest.raises(NotFound):
        views_meta.changelog.__wrapped__()

    app.config["LICENSE_FILE"] = str(tmp_path / "MISSING_LICENSE.txt")
    with app.app_context(), pytest.raises(NotFound):
        views_meta.license()
