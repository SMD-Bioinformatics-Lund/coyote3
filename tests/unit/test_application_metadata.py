"""Tests for repository-owned application metadata."""

from __future__ import annotations

from api.config.application_metadata import APPLICATION_DESCRIPTION, CODEBASE_LINKS


def test_application_metadata_contains_required_repository_links():
    """About, contact, and issue menus share one repository-owned source."""
    assert APPLICATION_DESCRIPTION
    assert CODEBASE_LINKS["repository_url"].startswith("https://github.com/")
    assert "template=bug_report.md" in CODEBASE_LINKS["bug_report_url"]
    assert "template=feature_request.md" in CODEBASE_LINKS["feature_request_url"]
    assert "template=support_request.md" in CODEBASE_LINKS["support_request_url"]
