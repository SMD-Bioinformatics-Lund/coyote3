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

"""Docs blueprint handbook routes."""

from __future__ import annotations

from pathlib import Path

from flask import abort, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.docs import docs_bp
from coyote.blueprints.docs.views_common import (
    can_view_developer_docs,
    render_markdown_file,
    search_handbook_docs,
)


@docs_bp.get("/")
@login_required
def docs_index():
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
    if rel.startswith("developer/") and not can_view_developer_docs():
        abort(403)

    handbook_html = render_markdown_file(requested)
    return render_template(
        "handbook_page.html",
        handbook_html=handbook_html,
        handbook_doc=doc_path,
    )
