
"""
This module provides a collection of Jinja2 template filters for use in Flask-based
genomic data analysis and reporting applications. The filters support common shared
filters, modifiers to display data in web templates.
"""

from flask import current_app as app
from datetime import datetime
from coyote.filters.shared import (
    format_comment_markdown as shared_format_comment_markdown,
    human_date as shared_human_date,
)


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
    return shared_human_date(value)


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
    return shared_format_comment_markdown(st)
