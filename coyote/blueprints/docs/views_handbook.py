"""Docs blueprint handbook routes."""

from __future__ import annotations

from pathlib import Path

from flask import abort, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.docs import docs_bp
from coyote.blueprints.docs.views_common import (
    render_markdown_file,
    search_handbook_docs,
)


@docs_bp.get("/")
@login_required
def docs_index():
    """Handle docs index.

    Returns:
        The function result.
    """
    q = request.args.get("q", "").strip()
    search_results = search_handbook_docs(q) if q else []
    return render_template(
        "index.html",
        q=q,
        search_results=search_results,
        search_count=len(search_results),
    )


@docs_bp.get("/user")
@login_required
def docs_user_index():
    """Handle docs user index.

    Returns:
        The function result.
    """
    return redirect(url_for("docs_bp.docs_page", doc_path="index.md"))


@docs_bp.get("/admin")
@login_required
def docs_admin_index():
    """Handle docs admin index.

    Returns:
        The function result.
    """
    return redirect(url_for("docs_bp.docs_page", doc_path="index.md"))


@docs_bp.get("/developer")
@login_required
def docs_developer_index():
    """Handle docs developer index.

    Returns:
        The function result.
    """
    return redirect(url_for("docs_bp.docs_page", doc_path="index.md"))


@docs_bp.get("/<path:doc_path>")
@login_required
def docs_page(doc_path: str):
    """
    Render a markdown page from docs root using /docs/<path>.md.
    """
    docs_root = Path(__file__).resolve().parents[3] / "docs"

    requested = (docs_root / doc_path).resolve()

    if not str(requested).startswith(str(docs_root.resolve())):
        abort(404)
    if requested.suffix.lower() != ".md":
        abort(404)

    rel = requested.relative_to(docs_root).as_posix()
    if rel.startswith("admin/"):
        abort(404)

    handbook_html = render_markdown_file(requested)
    return render_template(
        "handbook_page.html",
        handbook_html=handbook_html,
        handbook_doc=doc_path,
    )
