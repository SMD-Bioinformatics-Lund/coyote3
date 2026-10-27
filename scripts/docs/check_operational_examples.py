#!/usr/bin/env python3
"""Check documented shell syntax and repository script paths without executing examples."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL_BLOCK = re.compile(r"^```(?:bash|sh)\n(.*?)^```", re.MULTILINE | re.DOTALL)
SCRIPT_PATH = re.compile(
    r"(?<![\w/])((?:scripts|migrations_scripts)/[\w./-]+\.(?:py|sh|js|mjs))(?![\w.])"
)


def check_document(path: Path, *, root: Path) -> list[str]:
    """Collect invalid Bash blocks and references to removed repository scripts.

    Args:
        path: Markdown document to read, including fenced shell examples.
        root: Repository root used for checking literal script paths.

    Returns:
        Filename/line diagnostics. Bash runs with syntax checking only; examples
        are never sourced, expanded or executed. Dynamic paths are not resolved.
    """
    content = path.read_text(encoding="utf-8")
    errors = []
    for match in SHELL_BLOCK.finditer(content):
        result = subprocess.run(
            ["bash", "-n"], input=match[1], text=True, capture_output=True, check=False
        )
        if result.returncode:
            line = content[: match.start()].count("\n") + 1
            errors.append(f"{path}:{line}: invalid shell syntax: {result.stderr.strip()}")
    for match in SCRIPT_PATH.finditer(content):
        if not (root / match[1]).is_file():
            line = content[: match.start()].count("\n") + 1
            errors.append(f"{path}:{line}: script does not exist: {match[1]}")
    return errors


def main() -> int:
    """Check the root README and documentation without contacting services.

    Returns:
        Zero when all shell examples parse and literal script references exist.
        This does not establish command semantics, deployment success or readiness.
    """
    documents = [
        ROOT / "README.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "migrations_scripts").rglob("*.md")),
    ]
    errors = [error for path in documents for error in check_document(path, root=ROOT)]
    for error in errors:
        print(error)
    if errors:
        return 1
    print(f"[ok] shell syntax and script references checked in {len(documents)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
