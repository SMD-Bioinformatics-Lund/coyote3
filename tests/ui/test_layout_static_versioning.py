"""Regression tests for shell-level static asset versioning."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_layout_shell_uses_static_asset_macro_with_app_version():
    """The shared shell should route static assets through the versioned macro."""
    macro_source = (REPO_ROOT / "coyote/templates/macros/assets.html").read_text(encoding="utf-8")
    head_source = (REPO_ROOT / "coyote/templates/_partials/_head.html").read_text(encoding="utf-8")
    header_source = (REPO_ROOT / "coyote/templates/_partials/_header.html").read_text(
        encoding="utf-8"
    )
    flash_source = (REPO_ROOT / "coyote/templates/_partials/_flash.html").read_text(
        encoding="utf-8"
    )

    assert "v=config['APP_VERSION']" in macro_source
    assert '{% from "macros/assets.html" import static %}' in head_source
    assert "{{ static('css/tailwind.css') }}" in head_source
    assert "{{ static('js/api_client.js') }}" in head_source
    assert '{% from "macros/assets.html" import static %}' in header_source
    assert "{{ static('images/logo.png') }}" in header_source
    assert '{% from "macros/assets.html" import static %}' in flash_source
    assert "{{ static('icons/heroicons_outline_24/exclamation-circle.svg') }}" in flash_source
