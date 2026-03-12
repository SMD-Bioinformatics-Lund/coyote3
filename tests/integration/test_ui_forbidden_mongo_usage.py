"""Contract tests to ensure UI layer does not access Mongo directly."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FORBIDDEN_PATTERNS = [
    re.compile(r"^\s*(from|import)\s+pymongo\b", re.MULTILINE),
    re.compile(r"^\s*(from|import)\s+flask_pymongo\b", re.MULTILINE),
    re.compile(r"^\s*(from|import)\s+bson\b", re.MULTILINE),
    re.compile(r"^\s*(from|import)\s+motor\b", re.MULTILINE),
    re.compile(r"\bMongoClient\s*\(", re.MULTILINE),
    re.compile(r"\bPyMongo\s*\(", re.MULTILINE),
]


@pytest.mark.contract
def test_ui_layer_does_not_use_mongo_clients_or_drivers():
    """Handle test ui layer does not use mongo clients or drivers.

    Returns:
        The function result.
    """
    violations: list[str] = []

    for py_file in sorted(Path("coyote").rglob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in FORBIDDEN_PATTERNS):
            violations.append(str(py_file))

    assert not violations, (
        "UI layer must not touch Mongo directly.\n"
        "All business/data operations must go through API HTTP calls.\n" + "\n".join(violations)
    )
