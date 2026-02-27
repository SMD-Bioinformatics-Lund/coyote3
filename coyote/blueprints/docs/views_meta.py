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

"""Docs blueprint metadata routes (`about/changelog/license`)."""

from __future__ import annotations

from pathlib import Path

from flask import abort, render_template
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.docs import docs_bp
from coyote.blueprints.docs.views_common import render_markdown_file


@docs_bp.get("/about")
@login_required
def about():
    """
    About page for Coyote3:
      - app version
      - environment (dev/prod)
      - optional build metadata (git commit, build date)
    """
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

    safe_html = render_markdown_file(Path(file_path))
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
