"""Standard Shields.io badges preserve their logos, style and release metadata."""

import shutil
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.docs import generate_badges as badges

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """Build a small repository using actual package metadata and synthetic READMEs."""
    for filename in (
        "release.toml",
        "docker/Dockerfile",
        "frontend/package.json",
        *(f"{directory}/pyproject.toml" for directory in badges.PROJECTS.values()),
    ):
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    paths = []
    for filename in (
        "README.md",
        "core/README.md",
        "core/docs/README.md",
        "api/README.md",
        "adapters/mongo/README.md",
        "services/ingest/README.md",
        "services/ingest/docs/README.md",
        "api/src/coyote_api/bootstrap/demo_data/clinical_workflows/README.md",
    ):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Guide\n\nKeep this explanation.\n")
        paths.append(path)
    monkeypatch.setattr(badges, "readmes", lambda root: paths)
    return tmp_path


def test_original_shields_renderer_preserves_style_and_logo():
    markdown = badges.badge("Python", ">=3.12", "3776AB", "python")
    url = urlsplit(markdown.split("](", 1)[1][:-1])
    assert url.netloc == "img.shields.io"
    assert url.path == "/badge/Python-%3E%3D3.12-3776AB"
    assert parse_qs(url.query) == {"style": ["flat"], "logo": ["python"], "logoColor": ["white"]}
    assert "![Python: >=3.12]" in markdown


def test_package_and_license_hyphens_are_escaped_for_shields():
    markdown = badges.badge("coyote-core", "GPL-3.0-only")
    assert "/badge/coyote--core-GPL--3.0--only-" in markdown


def test_invalid_color_is_rejected():
    with pytest.raises(ValueError, match="RGB"):
        badges.badge("test", "value", 'red"/> ')


def test_generation_is_idempotent_and_preserves_explanations(repository):
    assert badges.generate(repository)
    assert badges.generate(repository) == []
    assert badges.generate(repository, check=True) == []
    for path in badges.readmes(repository):
        text = path.read_text()
        assert text.count(badges.START) == 1
        assert "Keep this explanation." in text
        assert "img.shields.io" in text
    demo = repository / "api/src/coyote_api/bootstrap/demo_data/clinical_workflows/README.md"
    assert "Synthetic%20data" in demo.read_text()
    assert "License" not in demo.read_text()
    readme = (repository / "README.md").read_text()
    groups = [
        "Build and validation",
        "Core Stack",
        "Domain & Capabilities",
        "Security & Governance",
    ]
    positions = [readme.index("### " + group) for group in groups]
    assert positions == sorted(positions)
    server_version = tomllib.loads((repository / "pyproject.toml").read_text())["project"][
        "version"
    ]
    for component in ("api", "adapters/mongo"):
        assert (
            f"![coyote-server: {server_version}]"
            in (repository / component / "README.md").read_text()
        )
    ingest_version = tomllib.loads((repository / "services/ingest/pyproject.toml").read_text())[
        "project"
    ]["version"]
    for filename in ("README.md", "docs/README.md"):
        assert (
            f"![coyote-ingest: {ingest_version}]"
            in (repository / "services/ingest" / filename).read_text()
        )


def test_check_mode_reports_metadata_drift_without_writing(repository):
    badges.generate(repository)
    metadata = repository / "core/pyproject.toml"
    current = tomllib.loads(metadata.read_text())["project"]["version"]
    metadata.write_text(metadata.read_text().replace(f'version = "{current}"', 'version = "4.2.3"'))
    readme = repository / "core/README.md"
    original = readme.read_bytes()
    assert "core/README.md" in badges.generate(repository, check=True)
    assert readme.read_bytes() == original
    badges.generate(repository)
    assert "4.2.3" in readme.read_text()
    assert badges.generate(repository, check=True) == []
