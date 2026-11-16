"""Build documentation from exactly the files copied into each docs image."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("dockerfile", ["Dockerfile.docs", "Dockerfile.docs.legacy"])
def test_documentation_image_inputs_publish_component_guides(tmp_path: Path, dockerfile: str):
    """Both container paths include the package guides and assets required by MkDocs."""
    builder = (ROOT / "docker" / dockerfile).read_text().split("\nFROM nginx:", 1)[0]
    for line in builder.splitlines():
        if not line.startswith("COPY "):
            continue
        arguments = shlex.split(line)[1:]
        if arguments[0] == "--from=center_config":
            arguments = [
                "api/src/coyote_api/config/examples/center/contact.toml",
                arguments[-1],
            ]
        destination = tmp_path / arguments[-1]
        for source_name in arguments[:-1]:
            source = ROOT / source_name
            assert source.exists(), f"Missing COPY input: {source_name}"
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                target = destination / source.name if arguments[-1].endswith("/") else destination
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"COYOTE4_CENTER_CONFIG_DIR", "ORGANIZATION_NAME", "ENV_NAME"}
    }
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for component in ("core", "api", "mongo", "client", "relay", "frontend"):
        assert (tmp_path / "site/packages" / component / "index.html").is_file()
        assert (tmp_path / "site/packages" / component / "overview/index.html").is_file()
    assert (tmp_path / "site/packages/api/assets/coyote-api-logo.svg").is_file()
    assert (tmp_path / "site/packages/relay/assets/coyote-relay-logo.svg").is_file()
    assert (tmp_path / "site/packages/server/pyproject.toml").is_file()
