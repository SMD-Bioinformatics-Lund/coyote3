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
web applications, specifically tailored for genomic data analysis, interpretation,
and clinical reporting. These filters enhance the presentation and usability of
data in web templates.
"""

from flask import current_app as app
from coyote.extensions import store
import os
import math
import markdown as md
from markupsafe import Markup


@app.template_filter()
def file_state(filepath: str | None) -> bool:
    """
    Check if a file exists at the given filepath and return its state.

    Args:
        filepath (str | None): The path to the file to check. Can be None.
    Returns:
        bool: True if the file exists, False otherwise.
    """
    if isinstance(filepath, list):
        filepath = filepath[0] if filepath else None
    if not filepath or filepath.lower() == "n/a":
        return False
    if os.path.exists(filepath):
        return True
    return False


@app.template_filter()
def isgl_adhoc_status(isgl_id: str) -> str:
    """
    Determine if an ISGL (In Silico Gene List) is temporary or permanent.

    Args:
        isgl_id (str): The name of the ISGL to check.
    Returns:
        bool: True if the ISGL is temporary, False otherwise.
    """
    return store.isgl_handler.is_isgl_adhoc(isgl_id)


@app.template_filter()
def isgl_display_name(isgl_id: str) -> str:
    """
    Get the display name for an ISGL (In Silico Gene List).

    Args:
        isgl_id (str): The name of the ISGL to get the display name for.
    Returns:
        str: The display name of the ISGL.
    """
    return store.isgl_handler.get_isgl_display_name(isgl_id)


@app.template_filter()
def human_filesize(file_path: str) -> str:
    """
    Convert a file size in bytes to a human-readable format.

    Args:
        file_path (str): The path to the file to get the size of.
    Returns:
        str: The file size in a human-readable format (e.g., '10.5 MB').
    """
    if not os.path.isfile(file_path):
        return "Not Available"
    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        return "Empty"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p: float = math.pow(1024, i)
    s: float = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


@app.template_filter()
def render_markdown(text: str) -> str:
    """
    Render Markdown to safe HTML using Python-Markdown.

    Args:
        text (str | None): Markdown source. If falsy, an empty string is returned.

    Returns:
        markupsafe.Markup: HTML-safe output produced with the 'extra', 'tables',
        and 'sane_lists' extensions enabled.
    """
    if not text:
        return ""
    html = md.markdown(text, extensions=["extra", "tables", "sane_lists"])
    return Markup(html)
