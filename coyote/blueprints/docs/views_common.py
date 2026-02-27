#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""Shared helpers for docs blueprint routes."""

from __future__ import annotations

from pathlib import Path

import bleach
from flask import abort
from flask_login import current_user
from markdown import markdown


ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "pre",
        "code",
        "ul",
        "ol",
        "li",
        "blockquote",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

ALLOWED_ATTRS = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "th": ["align"],
    "td": ["align"],
}


def render_markdown_file(md_path: Path) -> str:
    """Render a markdown file to sanitized HTML."""
    if not md_path.exists() or not md_path.is_file():
        abort(404)

    raw_md = md_path.read_text(encoding="utf-8", errors="replace")
    html = markdown(
        raw_md,
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        output_format="html5",
    )
    safe_html = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )
    return bleach.linkify(safe_html)


def can_view_developer_docs() -> bool:
    if not current_user.is_authenticated:
        return False
    return current_user.has_permission("delete_sample_global") or current_user.has_min_access_level(
        9999
    )


def search_handbook_docs(query: str, limit: int = 40) -> list[dict]:
    """
    Search markdown files under docs/handbook and return ranked matches.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    docs_root = Path(__file__).resolve().parents[3] / "docs" / "handbook"
    terms = [t for t in q.split() if t]
    if not terms:
        return []

    results: list[dict] = []
    can_view_developer = can_view_developer_docs()
    for md_path in sorted(docs_root.rglob("*.md")):
        rel = md_path.relative_to(docs_root).as_posix()
        if rel.startswith("admin/"):
            continue
        if rel.startswith("developer/") and not can_view_developer:
            continue
        try:
            raw = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        raw_l = raw.lower()
        hits = sum(1 for t in terms if t in raw_l)
        if hits == 0:
            continue

        title = md_path.stem.replace("-", " ").replace("_", " ").title()
        for line in raw.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        first_pos = min((raw_l.find(t) for t in terms if t in raw_l), default=0)
        start = max(0, first_pos - 80)
        end = min(len(raw), first_pos + 180)
        snippet = " ".join(raw[start:end].split())

        results.append(
            {
                "doc_path": rel,
                "title": title,
                "snippet": snippet,
                "score": hits,
            }
        )

    results.sort(key=lambda r: (-r["score"], r["doc_path"]))
    return results[:limit]
