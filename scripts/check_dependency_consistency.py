#!/usr/bin/env python3
"""Verify requirements exports match the authoritative pyproject declarations."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _normalize(requirement: str) -> str:
    value = requirement.strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", value)
    if match is None:
        return value.lower()
    name, specifier = match.groups()
    return f"{re.sub(r'[-_.]+', '-', name).lower()}{specifier.lower()}"


def _read_requirements(path: Path) -> set[str]:
    requirements: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-r "):
            continue
        requirements.add(_normalize(line))
    return requirements


def _declared(values: list[str]) -> set[str]:
    return {_normalize(value) for value in values}


def _check(label: str, expected: set[str], actual: set[str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"{label}: missing exports: {', '.join(missing)}")
    if extra:
        errors.append(f"{label}: undeclared exports: {', '.join(extra)}")
    return errors


def main() -> int:
    """Compare all requirements exports with their pyproject source groups."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    optional = project["optional-dependencies"]

    errors = _check(
        "requirements.txt",
        _declared(project["dependencies"]),
        _read_requirements(ROOT / "requirements.txt"),
    )
    errors.extend(
        _check(
            "requirements-dev.txt",
            _declared([*optional["dev"], *optional["test"]]),
            _read_requirements(ROOT / "requirements-dev.txt"),
        )
    )
    errors.extend(
        _check(
            "requirements-docs.txt",
            _declared(optional["docs"]),
            _read_requirements(ROOT / "requirements-docs.txt"),
        )
    )
    if errors:
        print("Dependency exports are inconsistent with pyproject.toml:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Dependency exports match pyproject.toml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
