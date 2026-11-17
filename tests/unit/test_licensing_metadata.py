"""Every first-party distribution retains consistent GPL terms and requested attribution."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_component_notices_preserve_copyright_affiliation_and_contributor_roles():
    copyright = (ROOT / "COPYRIGHT.txt").read_bytes()
    notice = (ROOT / "NOTICE.txt").read_bytes()
    license = (ROOT / "LICENSE.txt").read_bytes()
    assert b"GNU GENERAL PUBLIC LICENSE" in license
    assert b"Version 3, 29 June 2007" in license
    assert copyright.decode().splitlines()[1] == "Copyright © 2026 Ram Nanduri."
    assert "Sektion för molekylär diagnostik (SMD)" in copyright.decode()
    assert "Contributors\n------------\nViktor Henmyr\nSailendra Pradhananga" in copyright.decode()
    for name in ("core", "api", "adapters/mongo", "services/relay", "frontend"):
        directory = ROOT / name
        assert (directory / "COPYRIGHT.txt").read_bytes() == copyright
        assert (directory / "NOTICE.txt").read_bytes() == notice
        assert (directory / "LICENSE.txt").read_bytes() == license


def test_python_and_node_metadata_identify_gpl_and_keep_contributors_separate():
    for name in ("core", ".", "services/relay"):
        project = tomllib.loads((ROOT / name / "pyproject.toml").read_text())["project"]
        assert project["license"] == "GPL-3.0-only"
        assert "COPYRIGHT.txt" in project["license-files"]
        assert [author["name"] for author in project["authors"]] == ["Ram Nanduri"]
    for directory in (ROOT, ROOT / "frontend"):
        package = json.loads((directory / "package.json").read_text())
        lock = json.loads((directory / "package-lock.json").read_text())
        assert package["license"] == lock["packages"][""]["license"] == "GPL-3.0-only"
        assert package["author"] == "Ram Nanduri"
        assert [person["name"] for person in package["contributors"]] == [
            "Viktor Henmyr",
            "Sailendra Pradhananga",
        ]
