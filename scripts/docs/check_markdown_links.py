#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validate internal markdown links point to existing repo files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
LINK_OR_INLINE_CODE_RE = re.compile(
    r"(\[[^\]]+\]\([^)]+\)|(?m:^[ ]{0,3}\[[^\]\n]+\]:[^\n]*))|`[^`]*`"
)
REFERENCE_LINK_RE = re.compile(r"(?m)^[ ]{0,3}\[[^\]\n]+\]:\s*(<[^>]+>|\S+)")


def strip_code(text: str) -> str:
    """Remove code examples while retaining links whose labels contain inline code.

    Args:
        text: Markdown source containing prose, links and optional code examples.

    Returns:
        Source without fenced or inline code examples, preserving actual link targets.
    """
    text = CODE_FENCE_RE.sub("", text)
    text = LINK_OR_INLINE_CODE_RE.sub(lambda match: match[1] or "", text)
    return text


def is_external(target: str) -> bool:
    """Recognize supported web, mail, and telephone link prefixes.

    Args:
        target: Link target to inspect without trimming whitespace.

    Returns:
        Whether the target starts with HTTP, HTTPS, mailto, or tel, ignoring case.
    """
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:"))


def normalize_target(target: str) -> str:
    """Remove surrounding whitespace, angle brackets, fragments, and queries.

    Args:
        target: Raw Markdown link destination.

    Returns:
        Destination path or URL without its fragment or query; fragment-only links
        become empty strings. Percent-encoded characters are left unchanged.
    """
    cleaned = target.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.split("#", 1)[0]
    cleaned = cleaned.split("?", 1)[0]
    return cleaned


def main() -> int:
    """Check links in repository documentation after removing code examples.

    Returns:
        One after reporting absolute, escaping, or nonexistent local targets to
        stderr; zero after printing success. External and fragment-only links are skipped.

    Raises:
        OSError: A Markdown file cannot be read.
        subprocess.CalledProcessError: Git cannot enumerate maintained source files.
    """
    root = Path(__file__).resolve().parents[2]
    failures: list[str] = []

    maintained = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        text=True,
    )
    sources = {
        root / name
        for name in maintained.split("\0")
        if Path(name).suffix == ".md" and (root / name).is_file()
    }
    for md_file in sorted(sources):
        text = md_file.read_text(encoding="utf-8")
        text = strip_code(text)

        for raw_target in [*LINK_RE.findall(text), *REFERENCE_LINK_RE.findall(text)]:
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

    print(f"[ok] markdown internal links validated ({len(sources)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
