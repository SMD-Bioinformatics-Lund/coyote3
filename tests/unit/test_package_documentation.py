"""Package guides publish from one source with working repository and site links."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("package_docs", ROOT / "docs/hooks/packages.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


@pytest.fixture
def publication(tmp_path, monkeypatch):
    """Create independent package guides with a shared application overview."""
    for directory in ("docs", "core/docs"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "docs/README.md").write_text("# Application\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "coyote-server"\n')
    (tmp_path / "core/docs/README.md").write_text("# Core\n")
    (tmp_path / "core/docs/usage.md").write_text("# Usage\n")
    (tmp_path / "core/README.md").write_text("# Core project\n")
    (tmp_path / "core/docs/assets").mkdir()
    (tmp_path / "core/docs/assets/logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    config = MkDocsConfig()
    config.load_dict(
        {
            "site_name": "Test",
            "docs_dir": str(tmp_path / "docs"),
            "site_dir": str(tmp_path / "site"),
        }
    )
    errors, _ = config.validate()
    assert not errors
    files = Files([File("README.md", str(tmp_path / "docs"), config.site_dir, True)])
    monkeypatch.setattr(hook, "ROOT", tmp_path)
    monkeypatch.setattr(hook, "PROJECTS", {"core": "core"})

    class PackageGuides(BasePlugin):
        """Run package publication through the normal MkDocs event context."""

        on_files = staticmethod(hook.on_files)

    config.plugins["package-guides"] = PackageGuides()
    return tmp_path, config.plugins.on_files(files, config=config)


def test_published_page_uses_the_package_source(publication):
    root, files = publication
    guide = files.get_file_from_path("packages/core/README.md")
    assert Path(guide.abs_src_path) == root / "core/docs/README.md"
    assert guide.content_string == "# Core\n"
    assert files.get_file_from_path("packages/core/overview.md") is not None
    assert files.get_file_from_path("packages/core/assets/logo.svg") is not None
    metadata = files.get_file_from_path("packages/server/pyproject.toml")
    assert Path(metadata.abs_src_path) == root / "pyproject.toml"


@pytest.mark.parametrize(
    "page_uri,text,expected",
    [
        (
            "README.md",
            "[Server metadata](../pyproject.toml)",
            "[Server metadata](packages/server/pyproject.toml)",
        ),
        (
            "packages/core/overview.md",
            '<img src="docs/assets/logo.svg" alt="Core" width="360">',
            '<img src="../assets/logo.svg" alt="Core" width="360">',
        ),
        (
            "README.md",
            "[Core](../core/docs/README.md#usage)",
            "[Core](packages/core/README.md#usage)",
        ),
        ("packages/core/README.md", "[App](../../docs/README.md)", "[App](../../README.md)"),
        (
            "packages/core/README.md",
            "[Usage](usage.md?mode=read#start)",
            "[Usage](usage.md?mode=read#start)",
        ),
        ("README.md", "[core]: ../core/docs/usage.md\n", "[core]: packages/core/usage.md\n"),
        (
            "README.md",
            "[External](https://example.test) [Here](#start) [Unknown](missing.md)",
            "[External](https://example.test) [Here](#start) [Unknown](missing.md)",
        ),
    ],
)
def test_links_resolve_from_the_actual_source(publication, page_uri, text, expected):
    _, files = publication
    page = SimpleNamespace(file=files.get_file_from_path(page_uri))
    assert hook.on_page_markdown(text, page) == expected
