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
from flask import g
import os
import math
from coyote.filters.shared import render_markdown_rich as shared_render_markdown_rich
from coyote.integrations.api.api_client import (
    ApiRequestError,
    build_internal_headers,
    get_web_api_client,
)


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
    if not isgl_id:
        return False
    cache = getattr(g, "_isgl_meta_cache", None)
    if cache is None:
        cache = {}
        g._isgl_meta_cache = cache
    if isgl_id not in cache:
        try:
            cache[isgl_id] = get_web_api_client().get_json(
                f"/api/v1/internal/isgl/{isgl_id}/meta",
                headers=build_internal_headers(),
            )
        except ApiRequestError:
            return False
    return bool(cache[isgl_id].is_adhoc)


@app.template_filter()
def isgl_display_name(isgl_id: str) -> str:
    """
    Get the display name for an ISGL (In Silico Gene List).

    Args:
        isgl_id (str): The name of the ISGL to get the display name for.
    Returns:
        str: The display name of the ISGL.
    """
    if not isgl_id:
        return ""
    cache = getattr(g, "_isgl_meta_cache", None)
    if cache is None:
        cache = {}
        g._isgl_meta_cache = cache
    if isgl_id not in cache:
        try:
            cache[isgl_id] = get_web_api_client().get_json(
                f"/api/v1/internal/isgl/{isgl_id}/meta",
                headers=build_internal_headers(),
            )
        except ApiRequestError:
            return str(isgl_id)
    return str(cache[isgl_id].display_name or isgl_id)


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
    return shared_render_markdown_rich(text)
