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

"""
This module provides a collection of Jinja2 template filters for use in Flask-based
genomic data analysis and reporting applications. The filters support common shared
filters, modifiers to display data in web templates.
"""

from flask import current_app as app
import arrow
from dateutil import tz
from datetime import datetime, tzinfo
from markupsafe import Markup, escape
import markdown


STOCKHOLM: tzinfo | None = tz.gettz("Europe/Stockholm")


@app.template_filter(name="human_date")
def human_date(value: datetime | str) -> str:
    """
    Converts a date or datetime value to a human-readable relative time string
    (e.g., '3 days ago') in Central European Time (CET).

    Args:
        value (datetime | str): The input date or datetime string.

    Returns:
        str: A human-readable relative time string in CET timezone.
    """
    if not value:
        return "N/A"

    try:
        dt = arrow.get(value)

        # If it's naive, assume it is already Stockholm local time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=STOCKHOLM)

        dt = dt.to(STOCKHOLM)
        now = arrow.now(STOCKHOLM)

        return dt.humanize(now)
    except Exception:
        return "Invalid date"


@app.template_filter(name="format_comment")
def format_comment(st: str | None) -> str:
    """
    Render full GitHub-style markdown safely:
    - Supports headings (##)
    - Lists
    - Paragraphs
    - Bold/italics
    - Line breaks
    - Code blocks
    - Tables
    - Links
    - CRLF normalization
    """
    if not st:
        return ""

    # Normalize all newline types → "\n"
    st = st.replace("\r\n", "\n").replace("\r", "\n")

    # Escape unsafe HTML BEFORE markdown processing
    st = escape(st)

    # Render using GitHub-style markdown extensions
    html = markdown.markdown(
        st,
        extensions=[
            "extra",  # tables, code, lists, etc.
            "sane_lists",
            "nl2br",  # convert single newlines → <br>
            "toc",  # heading anchors
            "tables",  # GitHub table syntax
            "fenced_code",  # ``` code blocks
        ],
    )

    return Markup(html)
