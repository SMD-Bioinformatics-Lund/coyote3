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
Jinja2 template filters for the Coyote3 project.

This module defines custom Jinja2 filters for use in Flask templates,
including filters for formatting the current UTC datetime and pretty-printing
Python objects as JSON for HTML output.
"""


from flask import current_app as app
from coyote.util.misc import EnhancedJSONEncoder
from markupsafe import Markup
import json
from datetime import datetime, timezone
from typing import Any


@app.template_filter("now")
def now_filter(date_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Jinja2 filter that returns the current UTC datetime as a formatted string.

    Args:
        date_format (str): Datetime format string. Defaults to "%Y-%m-%d %H:%M:%S".

    Returns:
        str: Current UTC datetime formatted as a string.
    """
    return datetime.now(timezone.utc).strftime(date_format)


@app.template_filter("prettyjson")
def pretty_json_filter(value: Any) -> Markup:
    """
    Jinja2 filter that pretty-prints a Python object as JSON, safe for HTML.

    Args:
        value (Any): The Python object to serialize.

    Returns:
        Markup: HTML-safe, pretty-printed JSON string.
    """
    return Markup(json.dumps(value, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder))


@app.template_filter("safejson")
def safe_json_filter(value: Any) -> Any:
    """
    Jinja2 filter that serializes a Python object to JSON, safe for HTML.

    Args:
        value (Any): The Python object to serialize.

    Returns:
        Any: The JSON representation of the object, or None if serialization fails.
    """
    try:
        return json.loads(value)
    except Exception:
        return None
