#!/usr/bin/env python3
"""Validate internal markdown links point to existing repo files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def is_external(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:"))


def normalize_target(target: str) -> str:
    cleaned = target.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.split("#", 1)[0]
    cleaned = cleaned.split("?", 1)[0]
    return cleaned


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    docs_dir = root / "docs"
    failures: list[str] = []

    for md_file in docs_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = normalize_target(raw_target)
            if not target or is_external(target):
                continue
            if target.startswith("/"):
                failures.append(f"{md_file}: absolute local link not allowed: {raw_target}")
                continue

            resolved = (md_file.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                failures.append(f"{md_file}: escapes repo root: {raw_target}")
                continue

            if not resolved.exists():
                failures.append(f"{md_file}: missing target: {raw_target}")

    if failures:
        print("Markdown link validation failed:", file=sys.stderr)
        for line in failures:
            print(f" - {line}", file=sys.stderr)
        return 1

    print("[ok] markdown internal links validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

