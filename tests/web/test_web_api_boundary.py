"""Boundary tests to keep web layer independent from API internals."""

from __future__ import annotations

from pathlib import Path
import re


API_IMPORT_RE = re.compile(r"^\s*(from|import)\s+api[\.]", re.MULTILINE)
ALLOWED_FILES: set[str] = set()


def test_coyote_layer_does_not_import_api_modules_directly():
    violations: list[str] = []

    for py_file in sorted(Path("coyote").rglob("*.py")):
        rel = str(py_file)
        if rel in ALLOWED_FILES:
            continue
        content = py_file.read_text(encoding="utf-8")
        if API_IMPORT_RE.search(content):
            violations.append(rel)

    assert not violations, (
        "Direct 'api.*' imports in web layer are not allowed. "
        "Use coyote.services.api_client transport instead:\n" + "\n".join(violations)
    )
