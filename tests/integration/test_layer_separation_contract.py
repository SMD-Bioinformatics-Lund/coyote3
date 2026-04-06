"""Architecture guardrails for backend/frontend layer separation."""

from __future__ import annotations

import ast
from pathlib import Path


def test_frontend_layer_does_not_import_backend_api_modules() -> None:
    """Ensure ``coyote`` modules never import ``api`` Python modules directly."""
    offenders: list[str] = []
    for module_path in sorted(Path("coyote").rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "api" or alias.name.startswith("api."):
                        offenders.append(f"{module_path}:{node.lineno}:{alias.name}")
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if base == "api" or base.startswith("api."):
                    offenders.append(f"{module_path}:{node.lineno}:{base}")

    assert not offenders, (
        "Frontend layer (`coyote`) must not import backend (`api`) modules directly:\n"
        + "\n".join(offenders)
    )
