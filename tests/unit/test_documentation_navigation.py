"""Verify local documentation destinations and explicit task-path assembly."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.docs.check_built_site import check_site

HOOK = runpy.run_path(str(Path(__file__).resolve().parents[2] / "docs/hooks/reading.py"))


def test_sidebar_keeps_every_page_in_one_primary_location_and_starts_with_actions():
    """Readers can begin each task without first navigating a reference inventory."""
    root = Path(__file__).resolve().parents[2]
    navigation = yaml.safe_load((root / "mkdocs.yml").read_text().split("nav:\n", 1)[1])

    def destinations(items):
        """Flatten declared destinations without relying on the rendered theme."""
        return [
            page
            for item in items
            for value in item.values()
            for page in (destinations(value) if isinstance(value, list) else [value])
        ]

    pages = destinations(navigation)
    assert len(pages) == len(set(pages))
    assert all((root / "docs" / page).is_file() for page in pages)
    task_areas = navigation[1:-1]
    assert len(task_areas) <= 5
    for area in task_areas:
        first = next(iter(next(iter(area.values()))[0].values()))
        assert isinstance(first, str) and not first.endswith("README.md")


def test_optional_references_do_not_become_required_task_steps():
    """Recovery and authoring references stay outside the normal success path."""
    root = Path(__file__).resolve().parents[2]
    paths = yaml.safe_load((root / "docs/reading-paths.yml").read_text())["paths"]
    required = {entry["file"] for path in paths for entry in path["pages"]}
    assert not required.intersection(
        {
            "administration/query-rules.md",
            "administration/report-rule-authoring.md",
            "operations/ingest-job-recovery.md",
            "development/schema-contracts.md",
            "development/frontend-api-contracts.md",
        }
    )


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
