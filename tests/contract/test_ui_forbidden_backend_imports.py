"""Contract tests for UI-to-backend dependency boundaries."""

from __future__ import annotations

from pathlib import Path
import re


FORBIDDEN_IMPORT_RE = re.compile(r"^\s*(from|import)\s+api[\.]", re.MULTILINE)


def test_ui_layer_does_not_import_api_modules():
    violations: list[str] = []

    for py_file in sorted(Path("coyote").rglob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        if FORBIDDEN_IMPORT_RE.search(content):
            violations.append(str(py_file))

    assert not violations, (
        "UI layer must not import api.* internals.\n"
        "Use coyote.services.api_client (or integrations api transport) over HTTP instead.\n"
        + "\n".join(violations)
    )
