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

from flask import render_template, abort
from flask_login import login_required
from coyote.blueprints.docs import docs_bp
from flask import current_app as app
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


@docs_bp.get("/")
@login_required
def docs_index():
    return render_template("index.html")


@docs_bp.get("/<path:doc_path>")
@login_required
def docs_page(doc_path: str):
    """
    Render a handbook markdown page from docs/handbook using /handbook/<path>.md.
    """
    docs_root = Path(__file__).resolve().parents[3] / "docs" / "handbook"
    requested = (docs_root / doc_path).resolve()

    if not str(requested).startswith(str(docs_root.resolve())):
        abort(404)
    if requested.suffix.lower() != ".md":
        abort(404)

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
