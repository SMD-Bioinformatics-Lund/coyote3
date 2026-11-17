#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Verify requirements exports match the authoritative pyproject declarations."""

from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _normalize(requirement: str) -> str:
    """Normalize a requirement's name separators and lowercase its full declaration.

    Args:
        requirement: Dependency declaration including any specifier or extras.

    Returns:
        Stripped lowercase text with runs of dots, underscores, and hyphens in the
        leading package name replaced by one hyphen. Does not parse requirement syntax.
    """
    value = requirement.strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", value)
    if match is None:
        return value.lower()
    name, specifier = match.groups()
    return f"{re.sub(r'[-_.]+', '-', name).lower()}{specifier.lower()}"


def _read_requirements(path: Path) -> set[str]:
    """Collect normalized declarations, ignoring comments and ``-r`` include lines.

    Args:
        path: UTF-8 requirements export to read; included files are not traversed.

    Returns:
        Unique nonblank declarations after removing inline comments.

    Raises:
        OSError: The export cannot be read.
    """
    requirements: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-r "):
            continue
        requirements.add(_normalize(line))
    return requirements


def _declared(values: list[str]) -> set[str]:
    """Normalize and deduplicate a pyproject dependency group.

    Args:
        values: Requirement strings from a project dependency list.

    Returns:
        Unique declarations normalized for comparison with requirements exports.
    """
    return {_normalize(value) for value in values}


def group_requirements(
    groups: Mapping[str, Sequence[object]], name: str, ancestors: tuple[str, ...] = ()
) -> list[str]:
    """Resolve included development groups before comparing their requirements exports.

    Args:
        groups: Dependency groups declared in pyproject.toml.
        name: Group to expand.
        ancestors: Groups already being expanded, used to reject include cycles.

    Returns:
        Requirement strings from the group and its included groups.

    Raises:
        ValueError: A group is missing, contains an unsupported item or includes a cycle.
    """
    if name not in groups:
        raise ValueError(f"Unknown dependency group: {name}")
    if name in ancestors:
        raise ValueError(f"Cyclic dependency group: {' -> '.join((*ancestors, name))}")
    requirements = []
    for value in groups[name]:
        if isinstance(value, str):
            requirements.append(value)
        elif (
            isinstance(value, dict)
            and set(value) == {"include-group"}
            and isinstance(value["include-group"], str)
        ):
            requirements.extend(
                group_requirements(groups, value["include-group"], (*ancestors, name))
            )
        else:
            raise ValueError(f"Invalid dependency declaration in group {name}")
    return requirements


def _check(label: str, expected: set[str], actual: set[str]) -> list[str]:
    """Describe missing and undeclared dependency exports.

    Args:
        label: Export filename used to identify each diagnostic.
        expected: Normalized declarations from pyproject.
        actual: Normalized declarations read from the export.

    Returns:
        Missing-export diagnostic followed by undeclared-export diagnostic when
        applicable, each with sorted names; an empty list when the sets match.
    """
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
    optional = config["dependency-groups"]
    runtime = []
    local_names = {
        "coyote-core",
        "coyote-server",
        "coyote-pyclient",
        "coyote-relay",
        "coyote-atlas",
        "coyote-demo",
    }
    for relative in (
        ".",
        "core",
        "services/relay",
        "services/atlas",
        "services/demo",
    ):
        project = tomllib.loads((ROOT / relative / "pyproject.toml").read_text())["project"]
        for dependency in project["dependencies"]:
            name = re.split(r"[\[<>=!~; ]", _normalize(dependency), maxsplit=1)[0]
            if name not in local_names:
                runtime.append(dependency)

    # The independently maintained client is resolved by Git in uv.lock. Export
    # its direct runtime requirements without needing a second source checkout.
    packages = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    client = next(package for package in packages if package["name"] == "coyote-pyclient")
    for dependency in client["dependencies"]:
        matches = [
            package
            for package in packages
            if package["name"] == dependency["name"]
            and ("version" not in dependency or package["version"] == dependency["version"])
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Client runtime dependency is not uniquely locked: {dependency['name']}"
            )
        runtime.append(f"{dependency['name']}=={matches[0]['version']}")

    errors = _check(
        "requirements.txt",
        _declared(runtime),
        _read_requirements(ROOT / "requirements.txt"),
    )
    errors.extend(
        _check(
            "requirements-dev.txt",
            _declared(group_requirements(optional, "dev") + group_requirements(optional, "test")),
            _read_requirements(ROOT / "requirements-dev.txt"),
        )
    )
    errors.extend(
        _check(
            "requirements-docs.txt",
            _declared(group_requirements(optional, "docs")),
            _read_requirements(ROOT / "requirements-docs.txt"),
        )
    )
    errors.extend(
        _check(
            "requirements-load.txt",
            _declared(group_requirements(optional, "load")),
            _read_requirements(ROOT / "requirements-load.txt"),
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
