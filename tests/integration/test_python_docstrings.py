"""Require documentation on production Python definitions without importing services."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORIES = ("api", "scripts", "deploy/gunicorn")
DEFINITION_TYPES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _production_files() -> list[Path]:
    """Find application, operational-script and root-entrypoint Python sources.

    Returns:
        Sorted paths excluding caches, fixtures and dependency directories.
    """
    paths = set(ROOT.glob("*.py"))
    for directory in SOURCE_DIRECTORIES:
        paths.update(
            path for path in (ROOT / directory).rglob("*.py") if "__pycache__" not in path.parts
        )
    return sorted(paths)


@pytest.mark.parametrize("path", _production_files(), ids=lambda path: str(path.relative_to(ROOT)))
def test_production_definitions_have_docstrings(path: Path) -> None:
    """Keep modules, classes and named callables from losing their documentation."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    missing = []
    if tree.body and not ast.get_docstring(tree):
        missing.append("module")
    for node in ast.walk(tree):
        if isinstance(node, DEFINITION_TYPES) and not ast.get_docstring(node):
            missing.append(f"{node.name}:{node.lineno}")
    assert not missing, "Missing docstrings: " + ", ".join(missing)
