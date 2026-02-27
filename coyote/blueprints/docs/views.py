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
from __future__ import annotations

from flask import render_template, abort, request, redirect, url_for
from flask_login import login_required, current_user
from flask import current_app as app
from coyote.blueprints.docs import docs_bp
from pathlib import Path
from markdown import markdown
import bleach


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


def _render_markdown_file(md_path: Path) -> str:
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


def _search_handbook_docs(query: str, limit: int = 40) -> list[dict]:
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
    can_view_developer = _can_view_developer_docs()
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

        # Build a short snippet around the first hit term.
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


def _can_view_developer_docs() -> bool:
    if not current_user.is_authenticated:
        return False
    return current_user.has_permission("delete_sample_global") or current_user.has_min_access_level(
        9999
    )


@docs_bp.get("/")
@login_required
def docs_index():
    q = request.args.get("q", "").strip()
    search_results = _search_handbook_docs(q) if q else []
    return render_template(
        "index.html",
        q=q,
        search_results=search_results,
        search_count=len(search_results),
    )


@docs_bp.get("/user")
@login_required
def docs_user_index():
    return redirect(url_for("docs_bp.docs_page", doc_path="user/index.md"))


@docs_bp.get("/admin")
@login_required
def docs_admin_index():
    return redirect(url_for("docs_bp.docs_page", doc_path="index.md"))


@docs_bp.get("/developer")
@login_required
def docs_developer_index():
    return redirect(url_for("docs_bp.docs_page", doc_path="developer/index.md"))


@docs_bp.get("/<path:doc_path>")
@login_required
def docs_page(doc_path: str):
    """
    Render a handbook markdown page from docs/handbook using /handbook/<path>.md.
    """
    docs_root = Path(__file__).resolve().parents[3] / "docs" / "handbook"

    requested = (docs_root / doc_path).resolve()

    # Backward-compatible user-doc links like /handbook/04-dna-workflow.md
    # should resolve to /handbook/user/04-dna-workflow.md.
    if not requested.exists() and "/" not in doc_path:
        user_candidate = (docs_root / "user" / doc_path).resolve()
        if str(user_candidate).startswith(str(docs_root.resolve())) and user_candidate.exists():
            return redirect(url_for("docs_bp.docs_page", doc_path=f"user/{doc_path}"))

    if not str(requested).startswith(str(docs_root.resolve())):
        abort(404)
    if requested.suffix.lower() != ".md":
        abort(404)

    rel = requested.relative_to(docs_root).as_posix()
    if rel.startswith("admin/"):
        abort(404)
    if rel.startswith("developer/") and not _can_view_developer_docs():
        abort(403)

    handbook_html = _render_markdown_file(requested)
    return render_template(
        "handbook_page.html",
        handbook_html=handbook_html,
        handbook_doc=doc_path,
    )


@docs_bp.get("/about")
@login_required
def about():
    """
    About page for Coyote3:
      - app version
      - environment (dev/prod)
      - optional build metadata (git commit, build date)
    """
    # These are optional — only show if you set them in config
    meta = {
        "app_name": app.config.get("APP_NAME", "Coyote3"),
        "app_version": app.config.get("APP_VERSION", "unknown"),
        "environment": app.config.get("ENV_NAME", app.config.get("ENV", "unknown")),
        "git_commit": app.config.get("GIT_COMMIT", None),
        "build_time": app.config.get("BUILD_TIME", None),
        "changelog_in_app": bool(app.config.get("CHANGELOG_FILE")),
        "changelog_url": app.config.get("CHANGELOG_URL", None),
        "readme_url": app.config.get("README_URL"),
        "code_of_conduct_url": app.config.get("CODE_OF_CONDUCT_URL"),
        "security_url": app.config.get("SECURITY_URL"),
        "contributing_url": app.config.get("CONTRIBUTING_URL"),
    }
    return render_template("about.html", meta=meta)


@docs_bp.get("/changelog")
@login_required
def changelog():
    file_path = app.config.get("CHANGELOG_FILE")
    if not file_path:
        abort(404)

    safe_html = _render_markdown_file(Path(file_path))

    return render_template("changelog.html", changelog_html=safe_html)


@docs_bp.get("/license")
def license():
    """
    Render LICENSE.txt shipped with the application.
    """
    license_path = app.config.get("LICENSE_FILE", "LICENSE.txt")
    p = Path(license_path)

    if not p.exists() or not p.is_file():
        abort(404)

    license_text = p.read_text(encoding="utf-8", errors="replace")

    return render_template(
        "license.html",
        license_text=license_text,
    )
