"""Verify local documentation destinations and explicit task-path assembly."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.docs.check_built_site import check_site

HOOK = runpy.run_path(str(Path(__file__).resolve().parents[2] / "docs/hooks/reading.py"))


def test_built_site_checks_anchors_and_assets_without_external_requests(tmp_path):
    """Inspect actual HTML destinations rather than only Markdown filenames."""
    (tmp_path / "index.html").write_text(
        '<a href="guide/#step">Continue</a><a href="https://example.org/missing">External</a>'
        '<img src="diagram.svg"><script src="reading.js"></script>'
    )
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide/index.html").write_text('<h2 id="step">Step</h2><a href="../">Home</a>')
    (tmp_path / "diagram.svg").write_text("<svg/>")
    (tmp_path / "reading.js").write_text("")
    assert check_site(tmp_path) == (2, [])
    (tmp_path / "guide/index.html").write_text('<h2 id="renamed">Step</h2>')
    (tmp_path / "diagram.svg").unlink()
    count, errors = check_site(tmp_path)
    assert count == 2
    assert any("missing section anchor: guide/#step" in error for error in errors)
    assert any("missing destination: diagram.svg" in error for error in errors)


def test_built_site_requires_output_and_rejects_escaping_destinations(tmp_path):
    """Fail clearly when no build exists or a relative link leaves its directory."""
    assert check_site(tmp_path)[1]
    (tmp_path / "index.html").write_text('<a href="../private.html">Wrong</a>')
    assert "escapes built site" in check_site(tmp_path)[1][0]


def test_task_navigation_uses_declared_next_page_not_sidebar_order():
    """A task continuation resolves directly to its procedure and section anchor."""
    pages = [
        SimpleNamespace(file=SimpleNamespace(src_uri="first.md"), url="first/"),
        SimpleNamespace(file=SimpleNamespace(src_uri="reference.md"), url="reference/"),
        SimpleNamespace(file=SimpleNamespace(src_uri="finish.md"), url="finish/"),
    ]
    config = SimpleNamespace(
        extra={
            "reading_paths": [
                {
                    "title": "Complete a task",
                    "pages": [
                        {"file": "first.md", "label": "First"},
                        {"file": "finish.md", "label": "Finish", "anchor": "save"},
                    ],
                }
            ]
        }
    )
    context = HOOK["on_page_context"]({}, pages[0], config, SimpleNamespace(pages=pages))
    assert context["reading_path"]["next"]["url"] == "finish/#save"
    assert context["reading_path"]["previous"] is None
    assert HOOK["on_page_context"]({}, pages[1], config, SimpleNamespace(pages=pages)) == {}
    with pytest.raises(ValueError, match="unlisted page"):
        HOOK["on_page_context"]({}, pages[0], config, SimpleNamespace(pages=pages[:1]))
