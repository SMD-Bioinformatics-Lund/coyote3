"""Tests for repository-owned application metadata."""

from __future__ import annotations

from coyote_api.config.application_metadata import APPLICATION_DESCRIPTION, CODEBASE_LINKS


def test_api_package_version_is_separate_from_the_application_label(monkeypatch):
    """OpenAPI identifies the host package while product settings retain Coyote4's release."""
    from importlib.metadata import version

    from coyote_api import version as identity
    from coyote_api.app.main import app
    from coyote_api.config.runtime_settings import ProductionConfig

    assert app.version == identity.__version__ == version("coyote-api")
    assert ProductionConfig.APP_VERSION == identity.APPLICATION_VERSION
    monkeypatch.setattr(identity, "__version__", "99.0.0")
    assert identity.environment_version("production") == ProductionConfig.APP_VERSION


def test_application_metadata_contains_required_repository_links():
    """About, contact, and issue menus share one repository-owned source."""
    assert APPLICATION_DESCRIPTION
    assert CODEBASE_LINKS["repository_url"].startswith("https://github.com/")
    assert "template=bug_report.md" in CODEBASE_LINKS["bug_report_url"]
    assert "template=feature_request.md" in CODEBASE_LINKS["feature_request_url"]
    assert "template=support_request.md" in CODEBASE_LINKS["support_request_url"]
